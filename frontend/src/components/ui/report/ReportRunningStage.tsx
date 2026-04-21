"use client";

export function ReportRunningStage({
  progressLog,
  estimatedSeconds,
  onClose,
}: {
  progressLog: string[];
  estimatedSeconds: number;
  onClose: () => void;
}) {
  return (
    <div style={{ padding: "1rem 0", textAlign: "center" }}>
      <div
        style={{
          fontSize: "1.6rem",
          marginBottom: "0.75rem",
          display: "inline-block",
          animation: "spin 2s linear infinite",
        }}
      >
        {"\u27F3"}
      </div>
      <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Generating...</div>
      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
        Estimated ~{estimatedSeconds}s. You can close this dialog — it runs in the background.
      </div>

      {progressLog.length > 0 && (
        <div
          style={{
            background: "var(--bg-subtle)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "0.6rem 0.8rem",
            fontSize: "0.72rem",
            color: "var(--text-secondary)",
            textAlign: "left",
            maxHeight: 180,
            overflowY: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {progressLog.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}

      <button
        onClick={onClose}
        style={{
          marginTop: "1rem",
          padding: "0.45rem 1rem",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-sm)",
          background: "var(--bg-card)",
          cursor: "pointer",
          fontSize: "0.82rem",
        }}
      >
        Close (continues in background)
      </button>
    </div>
  );
}
