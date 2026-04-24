export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "-";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function parseNum(val: unknown): number | null {
  if (val == null || val === "") return null;
  const n = Number(val);
  return isNaN(n) ? null : n;
}

export function errorMessage(err: unknown, fallback = "Unknown error"): string {
  if (err instanceof Error) return err.message || fallback;
  if (typeof err === "string") return err || fallback;
  return fallback;
}

/**
 * Safely parse a CRM cell that may already be a parsed object, a JSON string,
 * or null/undefined/empty. Callers specify the expected shape via `<T>`; the
 * function performs no runtime shape validation — downstream components must
 * still guard against unexpected structures (and typically already do).
 */
export function safeJsonParse<T = unknown>(val: unknown): T | null {
  if (val == null || val === "") return null;
  if (typeof val === "object") return val as T;
  if (typeof val !== "string") return null;
  try {
    return JSON.parse(val) as T;
  } catch {
    return null;
  }
}
