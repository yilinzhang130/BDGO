/** SSR guard: true only when running in a browser with localStorage available. */
export function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

/** Fire-and-forget: swallow rejections with a labelled console.error. */
export function bg(promise: Promise<any>, label: string): void {
  promise.catch((err) => console.error(`[${label}]`, err));
}
