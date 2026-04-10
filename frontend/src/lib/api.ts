const BASE = "/api";

async function get<T = any>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== undefined && v !== null) url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

// Global Search
export const globalSearch = (q: string, limit = 5) =>
  get(`${BASE}/search/global`, { q, limit });

// Chat (returns raw Response for streaming)
export async function chatStream(message: string, sessionId: string, fileIds: string[] = []): Promise<Response> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, file_ids: fileIds }),
  });
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

// Buyers (MNC Profiles)
export const fetchBuyers = (params: Record<string, string | number>) =>
  get(`${BASE}/buyers`, params);
export const fetchBuyer = (name: string) =>
  get(`${BASE}/buyers/${encodeURIComponent(name)}`);

// Write (edit/delete)
export async function updateRecord(
  table: string, pk: string, fields: Record<string, string>, pk2?: string,
) {
  const res = await fetch(`${BASE}/write/${encodeURIComponent(table)}/${encodeURIComponent(pk)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields, pk2: pk2 || null }),
  });
  if (!res.ok) throw new Error(`Update failed: ${res.status}`);
  return res.json();
}

export async function deleteRecord(
  table: string, pk: string, pk2?: string,
) {
  const res = await fetch(`${BASE}/write/${encodeURIComponent(table)}/${encodeURIComponent(pk)}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pk2: pk2 || null }),
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
  return res.json();
}

// Tasks (agent automation)
export async function runTask(agent: string, message: string): Promise<{ task_id: string; status: string }> {
  const res = await fetch(`${BASE}/tasks/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent, message }),
  });
  if (!res.ok) throw new Error(`Task failed: ${res.status}`);
  return res.json();
}

export const fetchTaskStatus = (taskId: string) =>
  get(`${BASE}/tasks/status/${taskId}`);

// Upload
export async function uploadBP(file: File, company?: string): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  if (company) form.append("company", company);
  const res = await fetch(`${BASE}/upload/bp`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Upload failed: ${res.status} ${body}`);
  }
  return res.json();
}

// Reports (skill services)
export const fetchReportServices = () => get(`${BASE}/reports/list`);

export async function generateReport(slug: string, params: Record<string, any>): Promise<any> {
  const res = await fetch(`${BASE}/reports/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug, params }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Report generation failed: ${res.status}`);
  }
  return res.json();
}

export const fetchReportStatus = (taskId: string) =>
  get(`${BASE}/reports/status/${taskId}`);

export function reportDownloadUrl(taskId: string, format: string): string {
  return `${BASE}/reports/download/${taskId}/${format}`;
}

export async function renameCompany(oldName: string, newName: string): Promise<any> {
  const res = await fetch(`${BASE}/write/rename-company/${encodeURIComponent(oldName)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_name: newName }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Rename failed: ${res.status}`);
  }
  return res.json();
}

export const fetchDistinct = (table: string, column: string) =>
  get(`${BASE}/write/distinct/${encodeURIComponent(table)}/${encodeURIComponent(column)}`);
