import { getToken, clearAuth } from "./auth";

const BASE = "/api";

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function handle401(res: Response): void {
  if (res.status === 401) {
    clearAuth();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }
}

// Low-level fetch helpers. Default generic is ``any`` so legacy call
// sites that don't pass a type param don't regress; new code should
// supply the expected response type explicitly (or use one of the
// typed exports below).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function get<T = any>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== undefined && v !== null) url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString(), { headers: authHeaders() });
  handle401(res);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  handle401(res);
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function put<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  handle401(res);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = (await res.json()) as { detail?: string; message?: string };
      detail = j.detail ?? j.message ?? detail;
    } catch {
      // Non-JSON body — fall back to status code
    }
    throw new Error(detail);
  }
  return res.json();
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function patch<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  handle401(res);
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
  return res.json();
}

async function del(path: string): Promise<void> {
  const res = await fetch(path, { method: "DELETE", headers: authHeaders() });
  handle401(res);
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
}

// Auth / Profile
export const updateProfile = (fields: Record<string, string>) =>
  put(`${BASE}/auth/profile`, fields);

// Global Search — each category key maps to a list of matching rows.
// Row shape is per-category (company vs asset vs clinical etc.), so
// callers must narrow themselves. Kept loose to avoid coupling every
// caller to every row schema.
export interface GlobalSearchResponse {
  results: Record<string, Array<Record<string, unknown>>>;
}
export const globalSearch = (q: string, limit = 5) =>
  get<GlobalSearchResponse>(`${BASE}/search/global`, { q, limit });

// Session search
export const searchSessions = (q: string, limit = 6) =>
  get<{ id: string; title: string; updated_at: string }[]>(`${BASE}/sessions/search`, { q, limit });

// Chat (returns raw Response for streaming)
export type PlanMode = "auto" | "on" | "off";
export type SearchMode = "agent" | "quick";

export interface PlanConfirmPayload {
  plan_id: string;
  plan_title: string;
  selected_steps: {
    id: string;
    title: string;
    description: string;
    tools_expected: string[];
  }[];
  original_message: string;
}

export async function chatStream(
  message: string,
  sessionId: string,
  fileIds: string[] = [],
  modelId?: string,
  planMode: PlanMode = "auto",
  planConfirm?: PlanConfirmPayload,
  searchMode: SearchMode = "agent",
): Promise<Response> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      session_id: sessionId,
      file_ids: fileIds,
      ...(modelId ? { model_id: modelId } : {}),
      plan_mode: planMode,
      search_mode: searchMode,
      ...(planConfirm ? { plan_confirm: planConfirm } : {}),
    }),
  });
  handle401(res);
  if (!res.ok) {
    // Surface 402 credit-exhausted errors with their backend message
    let detail = `Chat failed: ${res.status}`;
    try {
      const body = (await res.clone().json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // Non-JSON error body — stick with the status-code message
    }
    throw new Error(detail);
  }
  return res;
}

// Credits + models
export interface CreditBalance {
  balance: number;
  total_granted: number;
  total_spent: number;
  updated_at: string | null;
}
export const fetchCreditBalance = () => get<CreditBalance>(`${BASE}/credits/balance`);

export interface CreditUsageItem {
  id: string | number;
  session_id: string | null;
  model_id: string;
  input_tokens: number;
  output_tokens: number;
  credits_charged: number;
  created_at: string;
}
export const fetchCreditUsage = (limit = 50) =>
  get<{ items: CreditUsageItem[] }>(`${BASE}/credits/usage`, { limit });

export interface ModelInfo {
  id: string;
  display_name: string;
  provider: string;
  input_weight: number;
  output_weight: number;
  context_note: string;
  available: boolean;
}
export const fetchModels = () => get<{ models: ModelInfo[] }>(`${BASE}/models`);

// Stats — each endpoint returns a single row or a flat list of {label, count}
// shaped records. Chart components consume these directly (via recharts).
export interface OverviewStats {
  companies: number;
  assets: number;
  clinical_records: number;
  deals: number;
  active_trials: number;
  tracked_companies: number;
}

export interface CountryCount {
  country: string;
  count: number;
}

export interface CompanyTypeCount {
  type: string;
  count: number;
}

export interface PhaseCount {
  phase: string;
  count: number;
}

export interface IndicationCount {
  indication: string;
  count: number;
}

export interface DealTypeCount {
  type: string;
  count: number;
}

export interface DealTimelinePoint {
  month: string;
  count: number;
  total_value: number;
}

export const fetchOverview = () => get<OverviewStats>(`${BASE}/stats/overview`);
export const fetchCompaniesByCountry = () =>
  get<CountryCount[]>(`${BASE}/stats/companies-by-country`);
export const fetchCompaniesByType = () =>
  get<CompanyTypeCount[]>(`${BASE}/stats/companies-by-type`);
export const fetchPipelineByPhase = () => get<PhaseCount[]>(`${BASE}/stats/pipeline-by-phase`);
export const fetchIndicationsTop = () => get<IndicationCount[]>(`${BASE}/stats/indications-top`);
export const fetchDealsByType = () => get<DealTypeCount[]>(`${BASE}/stats/deals-by-type`);
export const fetchDealsTimeline = () => get<DealTimelinePoint[]>(`${BASE}/stats/deals-timeline`);
// Companies
export const fetchCompanies = (params: Record<string, string | number>) =>
  get(`${BASE}/companies`, params);
export const fetchCompany = (name: string) => get(`${BASE}/companies/${encodeURIComponent(name)}`);
export const fetchCompanyAssets = (name: string, page = 1) =>
  get(`${BASE}/companies/${encodeURIComponent(name)}/assets`, { page });
export const fetchCompanyTrials = (name: string, page = 1) =>
  get(`${BASE}/companies/${encodeURIComponent(name)}/trials`, { page });
export const fetchCompanyDeals = (name: string) =>
  get(`${BASE}/companies/${encodeURIComponent(name)}/deals`);

// Assets
export const fetchAssets = (params: Record<string, string | number>) =>
  get(`${BASE}/assets`, params);
export const fetchAsset = (company: string, name: string) =>
  get(`${BASE}/assets/${encodeURIComponent(company)}/${encodeURIComponent(name)}`);
export const fetchAssetTrials = (company: string, name: string, page = 1) =>
  get(`${BASE}/assets/${encodeURIComponent(company)}/${encodeURIComponent(name)}/trials`, { page });

// Clinical
export const fetchClinical = (params: Record<string, string | number>) =>
  get(`${BASE}/clinical`, params);
export const fetchClinicalRecord = (id: string) =>
  get(`${BASE}/clinical/${encodeURIComponent(id)}`);

// Deals
export const fetchDeals = (params: Record<string, string | number>) => get(`${BASE}/deals`, params);
export const fetchDeal = (name: string) => get(`${BASE}/deals/${encodeURIComponent(name)}`);

// IP
export const fetchIP = (params: Record<string, string | number>) => get(`${BASE}/ip`, params);
export const fetchPatent = (id: string) => get(`${BASE}/ip/${encodeURIComponent(id)}`);

// Catalysts
export const fetchCatalysts = (params: Record<string, string | number>) =>
  get(`${BASE}/catalysts`, params);

// Buyers (MNC Profiles)
export const fetchBuyers = (params: Record<string, string | number>) =>
  get(`${BASE}/buyers`, params);
export const fetchBuyer = (name: string) => get(`${BASE}/buyers/${encodeURIComponent(name)}`);

// Write (edit/delete)
export const updateRecord = (
  table: string,
  pk: string,
  fields: Record<string, string>,
  pk2?: string,
) =>
  put(`${BASE}/write/${encodeURIComponent(table)}/${encodeURIComponent(pk)}`, {
    fields,
    pk2: pk2 || null,
  });

export async function deleteRecord(table: string, pk: string, pk2?: string) {
  // Uses DELETE with JSON body — can't use generic del() which has no body
  const res = await fetch(`${BASE}/write/${encodeURIComponent(table)}/${encodeURIComponent(pk)}`, {
    method: "DELETE",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ pk2: pk2 || null }),
  });
  handle401(res);
  if (!res.ok) throw new Error(`DELETE failed: ${res.status}`);
  return res.json();
}

// Tasks (agent automation)
export const runTask = (agent: string, message: string) =>
  post<{ task_id: string; status: string }>(`${BASE}/tasks/run`, { agent, message });

// Polling shape for both agent-task and report-task status endpoints.
// Shared because the backend returns the same schema for both flows.
export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress_log?: string[];
  error?: string | null;
  result?: {
    markdown?: string;
    files?: { filename: string; format: string; size: number; download_url: string }[];
    meta?: Record<string, unknown>;
  };
}

export const fetchTaskStatus = (taskId: string) =>
  get<TaskStatusResponse>(`${BASE}/tasks/status/${taskId}`);

// Upload with XHR so callers can receive progress events (Fetch has no upload progress)
export interface UploadBPResponse {
  file_id: string;
  filename: string;
  size: number;
  text_preview?: string;
}

export function uploadBP(
  file: File,
  company?: string,
  onProgress?: (pct: number) => void,
): Promise<UploadBPResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    if (company) form.append("company", company);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/upload/bp`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.timeout = 120_000;

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }

    xhr.onload = () => {
      if (xhr.status === 401) {
        clearAuth();
        if (typeof window !== "undefined" && window.location.pathname !== "/login")
          window.location.href = "/login";
        reject(new Error("Unauthorized"));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText.slice(0, 200)}`));
        return;
      }
      try {
        resolve(JSON.parse(xhr.responseText));
      } catch {
        reject(new Error("Invalid JSON response from upload"));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.ontimeout = () => reject(new Error("Upload timed out after 2 minutes"));
    xhr.send(form);
  });
}

// Reports (skill services)
export const fetchReportServices = () => get(`${BASE}/reports/list`);

export interface GenerateReportResponse {
  task_id: string;
  status: string;
  result?: TaskStatusResponse["result"];
}
export const generateReport = (slug: string, params: Record<string, unknown>) =>
  post<GenerateReportResponse>(`${BASE}/reports/generate`, { slug, params });

export const retryReport = (taskId: string) =>
  post<{ task_id: string; status: string; slug: string; estimated_seconds?: number }>(
    `${BASE}/reports/retry/${taskId}`,
  );

export const parseReportArgs = (slug: string, text: string) =>
  post<{ params: Record<string, unknown>; missing: string[]; complete: boolean }>(
    `${BASE}/reports/parse-args`,
    { slug, text },
  );

export const fetchReportStatus = (taskId: string) =>
  get<TaskStatusResponse>(`${BASE}/reports/status/${taskId}`);

export interface ReportTaskSummary {
  task_id: string;
  slug: string;
  title: string | null;
  status: string;
  created_at: string;
  finished_at: string | null;
  error: string | null;
}
export const fetchReportTasks = () => get<{ tasks: ReportTaskSummary[] }>(`${BASE}/reports/tasks`);

export function reportDownloadUrl(taskId: string, format: string): string {
  return `${BASE}/reports/download/${taskId}/${format}`;
}

export const renameCompany = (oldName: string, newName: string) =>
  post(`${BASE}/write/rename-company/${encodeURIComponent(oldName)}`, { new_name: newName });

export const fetchDistinct = (table: string, column: string) =>
  get(`${BASE}/write/distinct/${encodeURIComponent(table)}/${encodeURIComponent(column)}`);

// ═══════════════════════════════════════════
// Sessions
// ═══════════════════════════════════════════

// Server-side session shapes. The frontend store translates these into
// the richer ChatSession type via mapServerSession (see sessions.ts).
export interface ServerSessionSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServerSessionMessage {
  id: string;
  role: string;
  content: string;
  tools_json?: string;
  attachments_json?: string;
  created_at?: string;
}

export interface ServerSessionEntity {
  id: string;
  entity_type: string;
  title: string;
  subtitle?: string;
  fields_json?: string;
  href?: string;
  created_at?: string;
}

export interface ServerSessionDetail extends ServerSessionSummary {
  messages?: ServerSessionMessage[];
  context_entities?: ServerSessionEntity[];
}

export const fetchSessions = () => get<ServerSessionSummary[]>(`${BASE}/sessions`);

export const fetchSession = (id: string) => get<ServerSessionDetail>(`${BASE}/sessions/${id}`);

export const createSessionAPI = (title?: string) =>
  post<ServerSessionSummary>(`${BASE}/sessions`, { title });

export const renameSessionAPI = (id: string, title: string) =>
  put(`${BASE}/sessions/${id}`, { title });

export const deleteSessionAPI = (id: string) => del(`${BASE}/sessions/${id}`);

export const postMessage = (
  sessionId: string,
  msg: {
    id: string;
    role: string;
    content: string;
    tools_json?: string;
    attachments_json?: string;
  },
) => post(`${BASE}/sessions/${sessionId}/messages`, msg);

export const postEntity = (
  sessionId: string,
  entity: {
    id: string;
    entity_type: string;
    title: string;
    subtitle?: string;
    fields_json?: string;
    href?: string;
  },
) => post(`${BASE}/sessions/${sessionId}/entities`, entity);

export const deleteEntity = (sessionId: string, entityId: string) =>
  del(`${BASE}/sessions/${sessionId}/entities/${encodeURIComponent(entityId)}`);

// ═══════════════════════════════════════════
// Reports History
// ═══════════════════════════════════════════

// Server-side report shape. Translated by mapServerReport into
// CompletedReport in lib/reports.ts.
export interface ServerReportHistoryItem {
  id: string | number;
  task_id: string;
  slug: string;
  title: string | null;
  markdown_preview: string | null;
  files_json: string | null;
  meta_json: string | null;
  created_at: string;
}

export async function fetchReportsHistory(): Promise<ServerReportHistoryItem[]> {
  const resp = await get<{ history: ServerReportHistoryItem[] }>(`${BASE}/reports/history`);
  return resp.history || [];
}

export const deleteReportHistory = (id: string) =>
  del(`${BASE}/reports/history/${encodeURIComponent(id)}`);

// ═══════════════════════════════════════════
// Watchlist
// ═══════════════════════════════════════════

export const fetchWatchlist = (params: Record<string, string | number>) =>
  get(`${BASE}/watchlist`, params);

export interface WatchlistEntry {
  id: number;
  entity_type: string;
  entity_key: string;
  notes: string | null;
  added_at: string;
}
export const addToWatchlist = (body: { entity_type: string; entity_key: string; notes?: string }) =>
  post<WatchlistEntry>(`${BASE}/watchlist`, body);

export const removeFromWatchlist = (id: number) => del(`${BASE}/watchlist/${id}`);

export const checkWatchlist = (entity_type: string, entity_key: string) =>
  get<{ watched: boolean; id?: number }>(`${BASE}/watchlist/check`, { entity_type, entity_key });

// ═══════════════════════════════════════════
// Report Sharing
// ═══════════════════════════════════════════

export const createShareLink = (taskId: string) =>
  post<{ token: string; url: string }>(`${BASE}/reports/share`, { task_id: taskId });

export async function fetchSharedReport(token: string): Promise<{
  title: string;
  markdown_preview: string;
  files: { filename: string; format: string; size: number; download_url: string }[];
  created_at: string | null;
}> {
  const res = await fetch(`${BASE}/reports/share/${token}`);
  if (!res.ok) throw new Error(`Share fetch failed: ${res.status}`);
  return res.json();
}

// ═══════════════════════════════════════════
// Admin Dashboard
// ═══════════════════════════════════════════

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  is_admin: boolean;
  is_active: boolean;
  is_internal: boolean;
  company?: string;
  title?: string;
  created_at: string | null;
  last_login: string | null;
  credit_balance: number;
  total_granted: number;
  total_spent: number;
}

export interface InviteCode {
  id: string;
  code: string;
  note: string | null;
  max_uses: number;
  use_count: number;
  expires_at: string | null;
  created_at: string | null;
}

export const fetchAdminDashboard = () => get<{ users: AdminUser[] }>(`${BASE}/admin/dashboard`);

export const grantCredits = (userId: string, amount: number) =>
  post(`${BASE}/admin/credits/grant-ui`, { user_id: userId, amount });

export const fetchAdminInviteCodes = () =>
  get<{ codes: InviteCode[] }>(`${BASE}/admin/invite-codes-ui`);

export const createInviteCode = (maxUses: number = 1) =>
  post<InviteCode>(`${BASE}/admin/invite-codes-ui`, { max_uses: maxUses });

export const deleteInviteCode = (code: string) =>
  del(`${BASE}/admin/invite-codes-ui/${encodeURIComponent(code)}`);

export const setUserActive = (userId: string, value: boolean) =>
  post(`${BASE}/admin/users/set-active-ui`, { user_id: userId, value });

export const setUserAdmin = (userId: string, value: boolean) =>
  post(`${BASE}/admin/users/set-admin-ui`, { user_id: userId, value });

export const setUserInternal = (userId: string, value: boolean) =>
  post(`${BASE}/admin/users/set-internal-ui`, { user_id: userId, value });

// ── Inbox ─────────────────────────────────────────────────────────────────────

export interface InboxMessage {
  id: number;
  type: "data_report" | "feedback";
  user_email: string;
  user_name: string;
  entity_type: string | null;
  entity_key: string | null;
  entity_url: string | null;
  message: string;
  read_at: string | null;
  created_at: string;
}

export const fetchInboxMessages = (unreadOnly = false, limit = 50, offset = 0) =>
  get<{ total: number; items: InboxMessage[] }>(`${BASE}/inbox/admin/messages`, {
    unread_only: unreadOnly ? 1 : 0,
    limit,
    offset,
  });

export const fetchInboxUnreadCount = () =>
  get<{ count: number }>(`${BASE}/inbox/admin/unread-count`);

export const markMessageRead = (id: number) => patch(`${BASE}/inbox/admin/messages/${id}/read`);

export const markAllRead = () => patch(`${BASE}/inbox/admin/messages/read-all`);

// ── Conference Insight ─────────────────────────────────────────────────────────

export interface ConferenceSession {
  id: string;
  name: string;
  full_name: string;
  date: string;
  location: string;
  type: string;
  total_bd_heat_companies?: number;
  total_abstracts_covered?: number;
}

export interface ConferenceAbstractPreview {
  doi: string;
  title: string;
  kind: string;
  targets: string[];
  data_points: Record<string, string>;
}

export interface ConferenceCompanyCard {
  company: string;
  客户类型: string;
  所处国家: string;
  Ticker: string | null;
  市值估值: string | null;
  CT_count: number;
  LB_count: number;
  abstract_count: number;
  top_abstracts: ConferenceAbstractPreview[];
}

export interface ConferenceListResponse {
  data: ConferenceCompanyCard[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: { types: string[]; countries: string[] };
}

export const fetchConferenceSessions = () =>
  get<{ sessions: ConferenceSession[] }>(`${BASE}/conference/sessions`);

export const fetchConferenceStats = (sessionId: string) =>
  get(`${BASE}/conference/${encodeURIComponent(sessionId)}/stats`);

export const fetchConferenceCompanies = (
  sessionId: string,
  params: {
    q?: string;
    company_type?: string;
    country?: string;
    ct_only?: boolean;
    page?: number;
    page_size?: number;
  } = {},
) =>
  get<ConferenceListResponse>(`${BASE}/conference/${encodeURIComponent(sessionId)}/companies`, {
    ...(params.q ? { q: params.q } : {}),
    ...(params.company_type ? { company_type: params.company_type } : {}),
    ...(params.country ? { country: params.country } : {}),
    ...(params.ct_only ? { ct_only: 1 } : {}),
    page: params.page ?? 1,
    page_size: params.page_size ?? 24,
  });

export const fetchConferenceCompany = (sessionId: string, companyName: string) =>
  get(
    `${BASE}/conference/${encodeURIComponent(sessionId)}/companies/${encodeURIComponent(companyName)}`,
  );

export interface ConferenceAbstract {
  doi: string;
  title: string;
  kind: "CT" | "LB" | "regular";
  targets: string[];
  data_points: Record<string, string>;
  conclusion?: string;
  ncts?: string[];
  company: string;
  客户类型: string;
  所处国家: string;
  Ticker?: string | null;
}

export interface ConferenceAbstractsResponse {
  data: ConferenceAbstract[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: { companies: string[]; countries: string[]; types: string[] };
}

export const fetchConferenceAbstracts = (
  sessionId: string,
  params: {
    q?: string;
    kind?: string;
    company?: string;
    country?: string;
    company_type?: string;
    page?: number;
    page_size?: number;
  } = {},
) =>
  get<ConferenceAbstractsResponse>(
    `${BASE}/conference/${encodeURIComponent(sessionId)}/abstracts`,
    {
      ...(params.q ? { q: params.q } : {}),
      ...(params.kind ? { kind: params.kind } : {}),
      ...(params.company ? { company: params.company } : {}),
      ...(params.country ? { country: params.country } : {}),
      ...(params.company_type ? { company_type: params.company_type } : {}),
      page: params.page ?? 1,
      page_size: params.page_size ?? 24,
    },
  );

// ---------------------------------------------------------------------------
// API Keys (developer portal)
// ---------------------------------------------------------------------------

export interface ApiKeyRecord {
  id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  quota_daily: number | null;
  created_at: string;
  last_used_at: string | null;
  last_used_ip: string | null;
  revoked_at: string | null;
  expires_at: string | null;
  is_active: boolean;
}

export const fetchApiKeys = (includeRevoked = false) =>
  get<{ items: ApiKeyRecord[] }>(
    `${BASE}/keys`,
    includeRevoked ? { include_revoked: "true" } : undefined,
  );

export const createApiKey = (name: string, quotaDaily?: number) =>
  post<{ key: string; record: ApiKeyRecord }>(`${BASE}/keys`, {
    name,
    ...(quotaDaily !== undefined ? { quota_daily: quotaDaily } : {}),
  });

export const revokeApiKey = (keyId: string) =>
  fetch(`${BASE}/keys/${encodeURIComponent(keyId)}`, {
    method: "DELETE",
    headers: authHeaders(),
  }).then(async (res) => {
    handle401(res);
    if (!res.ok) throw new Error(`Revoke failed: ${res.status}`);
    return res.json() as Promise<ApiKeyRecord>;
  });
