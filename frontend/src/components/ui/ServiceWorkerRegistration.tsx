"use client";

/**
 * ServiceWorkerRegistration (P3-13)
 *
 * Registers /sw.js on mount. No-op in dev (NODE_ENV !== production) to avoid
 * caching stale assets during development. Safe to render in any layout.
 */

import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !("serviceWorker" in navigator) ||
      process.env.NODE_ENV !== "production"
    ) {
      return;
    }

    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .catch((err) => console.warn("[SW] registration failed:", err));
  }, []);

  return null;
}
