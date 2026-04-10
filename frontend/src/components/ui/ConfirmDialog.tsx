"use client";

interface Props {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ message, onConfirm, onCancel }: Props) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-card)", borderRadius: 12, padding: "1.5rem",
          maxWidth: 400, width: "90%", boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
        }}
      >
        <p style={{ margin: "0 0 1.25rem", fontSize: "0.95rem" }}>{message}</p>
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
          <button
            onClick={onCancel}
            style={{
              padding: "0.45rem 1rem", border: "1px solid var(--border)",
              borderRadius: 6, background: "var(--bg-card)", cursor: "pointer", fontSize: "0.85rem",
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: "0.45rem 1rem", border: "none",
              borderRadius: 6, background: "var(--red)", color: "white",
              cursor: "pointer", fontSize: "0.85rem", fontWeight: 600,
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
