"use client";

export function ReportErrorStage({
  message,
  onRetry,
  onClose,
}: {
  message: string;
  onRetry: () => void;
  onClose: () => void;
}) {
  return (
    <div style={{ padding: "1.5rem 0", textAlign: "center" }}>
      <div style={{ fontSize: "2rem", color: "var(--red)", marginBottom: "0.5rem" }}>
        {"\u2715"}
      </div>
      <div style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Generation Failed</div>
      <div
        style={{
          fontSize: "0.78rem",
          color: "var(--text-secondary)",
          marginBottom: "1.25rem",
          padding: "0.5rem 0.75rem",
          background: "rgba(220,38,38,0.08)",
          borderRadius: "var(--radius-sm)",
          maxHeight: 120,
          overflowY: "auto",
        }}
      >
        {message}
      </div>
      <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
        <button
          onClick={onRetry}
          style={{
            padding: "0.45rem 1rem",
            border: "none",
            borderRadius: "var(--radius-sm)",
            background: "var(--accent)",
            color: "white",
            cursor: "pointer",
            fontSize: "0.82rem",
            fontWeight: 600,
          }}
        >
          Try Again
        </button>
        <button
          onClick={onClose}
          style={{
            padding: "0.45rem 1rem",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-card)",
            cursor: "pointer",
            fontSize: "0.82rem",
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}
