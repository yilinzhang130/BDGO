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

async function put<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  handle401(res);
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
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

// Global Search
export const globalSearch = (q: string, limit = 5) =>
  get(`${BASE}/search/global`, { q, limit });

// Session search
export const searchSessions = (q: string, limit = 6) =>
  get<{ id: string; title: string; updated_at: string }[]>(`${BASE}/sessions/search`, { q, limit });

// Chat (returns raw Response for streaming)
export async function chatStream(message: string, sessionId: string, fileIds: string[] = []): Promise<Response> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, session_id: sessionId, file_ids: fileIds }),
  });
  handle401(res);
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res;
}

// Stats
export const fetchOverview = () => get(`${BASE}/stats/overview`);
export const fetchCompaniesByCountry = () => get(`${BASE}/stats/companies-by-country`);
export const fetchCompaniesByType = () => get(`${BASE}/stats/companies-by-type`);
export const fetchPipelineByPhase = () => get(`${BASE}/stats/pipeline-by-phase`);
export const fetchIndicationsTop = () => get(`${BASE}/stats/indications-top`);
export const fetchDealsByType = () => get(`${BASE}/stats/deals-by-type`);
export const fetchDealsTimeline = () => get(`${BASE}/stats/deals-timeline`);
// Companies
export const fetchCompanies = (params: Record<string, string | number>) =>
  get(`${BASE}/companies`, params);
export const fetchCompany = (name: string) =>
  get(`${BASE}/companies/${encodeURIComponent(name)}`);
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
export const fetchDeals = (params: Record<string, string | number>) =>
  get(`${BASE}/deals`, params);
export const fetchDeal = (name: string) =>
  get(`${BASE}/deals/${encodeURIComponent(name)}`);

// IP
export const fetchIP = (params: Record<string, string | number>) =>
  get(`${BASE}/ip`, params);
export const fetchPatent = (id: string) =>
  get(`${BASE}/ip/${encodeURIComponent(id)}`);

// Catalysts
export const fetchCatalysts = (params: Record<string, string | number>) =>
  get(`${BASE}/catalysts`, params);

// Buyers (MNC Profiles)
export const fetchBuyers = (params: Record<string, string | number>) =>
  get(`${BASE}/buyers`, params);
export const fetchBuyer = (name: string) =>
  get(`${BASE}/buyers/${encodeURIComponent(name)}`);

// Write (edit/delete)
export const updateRecord = (
  table: string, pk: string, fields: Record<string, string>, pk2?: string,
) => put(`${BASE}/write/${encodeURIComponent(table)}/${encodeURIComponent(pk)}`, { fields, pk2: pk2 || null });

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

export const fetchTaskStatus = (taskId: string) =>
  get(`${BASE}/tasks/status/${taskId}`);

// Upload with XHR so callers can receive progress events (Fetch has no upload progress)
export function uploadBP(
  file: File,
  company?: string,
  onProgress?: (pct: number) => void,
): Promise<any> {
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
      try { resolve(JSON.parse(xhr.responseText)); }
      catch { reject(new Error("Invalid JSON response from upload")); }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.ontimeout = () => reject(new Error("Upload timed out after 2 minutes"));
    xhr.send(form);
  });
}

// Reports (skill services)
export const fetchReportServices = () => get(`${BASE}/reports/list`);

export const generateReport = (slug: string, params: Record<string, any>) =>
  post(`${BASE}/reports/generate`, { slug, params });

export const fetchReportStatus = (taskId: string) =>
  get(`${BASE}/reports/status/${taskId}`);

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

export const fetchSessions = () => get<any[]>(`${BASE}/sessions`);

export const fetchSession = (id: string) => get<any>(`${BASE}/sessions/${id}`);

export const createSessionAPI = (title?: string) =>
  post(`${BASE}/sessions`, { title });

export const renameSessionAPI = (id: string, title: string) =>
  put(`${BASE}/sessions/${id}`, { title });

export const deleteSessionAPI = (id: string) =>
  del(`${BASE}/sessions/${id}`);

export const postMessage = (
  sessionId: string,
  msg: { id: string; role: string; content: string; tools_json?: string; attachments_json?: string },
) => post(`${BASE}/sessions/${sessionId}/messages`, msg);

export const postEntity = (
  sessionId: string,
  entity: { id: string; entity_type: string; title: string; subtitle?: string; fields_json?: string; href?: string },
) => post(`${BASE}/sessions/${sessionId}/entities`, entity);

export const deleteEntity = (sessionId: string, entityId: string) =>
  del(`${BASE}/sessions/${sessionId}/entities/${encodeURIComponent(entityId)}`);

// ═══════════════════════════════════════════
// Reports History
// ═══════════════════════════════════════════

export async function fetchReportsHistory(): Promise<any[]> {
  const resp = await get<{ history: any[] }>(`${BASE}/reports/history`);
  return resp.history || [];
}

export const deleteReportHistory = (id: string) =>
  del(`${BASE}/reports/history/${encodeURIComponent(id)}`);

// ═══════════════════════════════════════════
// Watchlist
// ═══════════════════════════════════════════

export const fetchWatchlist = (params: Record<string, string | number>) =>
  get(`${BASE}/watchlist`, params);

export const addToWatchlist = (body: { entity_type: string; entity_key: string; notes?: string }) =>
  post(`${BASE}/watchlist`, body);

export const removeFromWatchlist = (id: number) =>
  del(`${BASE}/watchlist/${id}`);

export const checkWatchlist = (entity_type: string, entity_key: string) =>
  get<{ watched: boolean; id?: number }>(`${BASE}/watchlist/check`, { entity_type, entity_key });

// ═══════════════════════════════════════════
// Report Sharing
// ═══════════════════════════════════════════

export const createShareLink = (taskId: string) =>
  post<{ token: string; url: string }>(`${BASE}/reports/share`, { task_id: taskId });

export async function fetchSharedReport(token: string): Promise<{ title: string; markdown_preview: string; files: { filename: string; format: string; size: number; download_url: string }[]; created_at: string | null }> {
  const res = await fetch(`${BASE}/reports/share/${token}`);
  if (!res.ok) throw new Error(`Share fetch failed: ${res.status}`);
  return res.json();
}
