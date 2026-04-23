/** SSR guard: true only when running in a browser with localStorage available. */
export function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

/** Fire-and-forget: swallow rejections with a labelled console.error. */
export function bg(promise: Promise<any>, label: string): void {
  promise.catch((err) => console.error(`[${label}]`, err));
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "-";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function parseNum(val: any): number | null {
  if (val == null || val === "") return null;
  const n = Number(val);
  return isNaN(n) ? null : n;
}

export function phaseBadgeClass(phase: string): string {
  if (!phase) return "badge-gray";
  const p = phase.toLowerCase();
  if (p.includes("approved") || p.includes("上市")) return "badge-green";
  if (p.includes("3")) return "badge-blue";
  if (p.includes("2")) return "badge-purple";
  if (p.includes("1")) return "badge-amber";
  if (p.includes("pre")) return "badge-gray";
  return "badge-gray";
}

export function priorityBadgeClass(priority: string): string {
  if (!priority) return "badge-gray";
  if (priority === "A") return "badge-green";
  if (priority === "B") return "badge-blue";
  return "badge-gray";
}

export function resultBadgeClass(result: string): string {
  if (!result) return "badge-gray";
  if (result.includes("积极") || result.includes("positive")) return "badge-green";
  if (result.includes("阴性") || result.includes("negative") || result.includes("未达成"))
    return "badge-red";
  if (result.includes("混合")) return "badge-amber";
  return "badge-gray";
}

export function statusBadgeClass(status: string): string {
  if (status === "有效") return "badge-green";
  if (status === "已过期") return "badge-red";
  return "badge-gray";
}

export function safeJsonParse(val: any): any {
  if (!val) return null;
  if (typeof val === "object") return val;
  try {
    return JSON.parse(val);
  } catch {
    return null;
  }
}

// Chart colors palette
export const COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#6366f1",
  "#84cc16",
  "#06b6d4",
  "#e11d48",
  "#a855f7",
  "#22c55e",
  "#eab308",
  "#0ea5e9",
  "#d946ef",
  "#64748b",
  "#f43f5e",
  "#2dd4bf",
];
