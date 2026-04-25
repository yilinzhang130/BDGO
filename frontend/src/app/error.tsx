"use client";

/**
 * Global Next.js App Router error boundary.
 *
 * Catches unhandled errors thrown by Server Components (e.g. when the backend
 * is unavailable and serverGet() throws). Without this file, Next.js renders
 * its own internal error page which may expose stack traces to the browser.
 *
 * Per-route error.tsx files can override this for more specific messages.
 */

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console in dev; wire to Sentry / LogRocket in prod if needed.
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "4rem 2rem",
        textAlign: "center",
        gap: "1rem",
      }}
    >
      <h2 style={{ fontSize: "1.25rem", fontWeight: 600 }}>无法加载数据</h2>
      <p style={{ color: "var(--muted)", maxWidth: 360 }}>
        服务暂时不可用，请稍后重试。如果问题持续，请联系管理员。
      </p>
      {error.digest && (
        <p style={{ fontSize: "0.75rem", color: "var(--muted)", fontFamily: "monospace" }}>
          错误代码: {error.digest}
        </p>
      )}
      <button
        onClick={reset}
        style={{
          padding: "0.5rem 1.5rem",
          borderRadius: "6px",
          border: "1px solid var(--border)",
          background: "var(--accent)",
          color: "#fff",
          cursor: "pointer",
          fontSize: "0.9rem",
        }}
      >
        重试
      </button>
    </div>
  );
}
