"use client";

/**
 * OfflineIndicator (P3-13)
 *
 * Shows a slim banner at the top of the screen when the browser is offline.
 * Disappears automatically when connectivity is restored.
 */

import { useEffect, useState } from "react";

export function OfflineIndicator() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    // Hydrate once from current state after mount (avoids SSR mismatch)
    sync();
    window.addEventListener("offline", sync);
    window.addEventListener("online", sync);
    return () => {
      window.removeEventListener("offline", sync);
      window.removeEventListener("online", sync);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        background: "#1E3A8A",
        color: "#fff",
        fontSize: 13,
        fontWeight: 600,
        textAlign: "center",
        padding: "7px 16px",
        letterSpacing: "0.01em",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <span style={{ marginRight: 8 }}>📶</span>
      离线模式 — 已显示缓存数据
    </div>
  );
}
