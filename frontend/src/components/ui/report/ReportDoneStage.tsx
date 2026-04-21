"use client";

export function ReportDoneStage({
  result,
  onClose,
}: {
  result: any;
  onClose: () => void;
}) {
  const files = result.files || [];
  const markdownPreview = (result.markdown || "").slice(0, 400);

  return (
    <div style={{ padding: "0.5rem 0", display: "flex", flexDirection: "column" }}>
      <div style={{ textAlign: "center", marginBottom: "1rem" }}>
        <div style={{ fontSize: "2rem", color: "var(--green)", marginBottom: "0.3rem" }}>
          {"\u2713"}
        </div>
        <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>Report Complete</div>
      </div>

      {markdownPreview && (
        <div
          style={{
            background: "var(--bg-subtle)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "0.75rem",
            fontSize: "0.78rem",
            color: "var(--text-secondary)",
            whiteSpace: "pre-wrap",
            maxHeight: 200,
            overflowY: "auto",
            lineHeight: 1.5,
            marginBottom: "1rem",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {markdownPreview}
          {result.markdown && result.markdown.length > 400 ? "\n..." : ""}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          justifyContent: "flex-end",
          paddingTop: "0.75rem",
          borderTop: "1px solid var(--border)",
        }}
      >
        {files.map((f: any) => (
          <a
            key={f.filename}
            href={f.download_url}
            download={f.filename}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: "0.45rem 1rem",
              background: "var(--accent)",
              color: "white",
              textDecoration: "none",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.82rem",
              fontWeight: 600,
            }}
          >
            {"\u2B07 Download ."}{f.format}
          </a>
        ))}
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
