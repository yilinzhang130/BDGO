"use client";

import { useState, useRef, useEffect } from "react";
import { errorMessage } from "@/lib/format";

interface Props {
  label: string;
  value: string;
  onSave: (newValue: string) => Promise<void>;
}

export function EditableField({ label, value, onSave }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const save = async () => {
    if (draft === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } catch (err: unknown) {
      alert(`保存失败: ${errorMessage(err, "未知错误")}`);
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
        <span style={{ color: "var(--text-secondary)", minWidth: 80 }}>{label}:</span>
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") {
              setDraft(value);
              setEditing(false);
            }
          }}
          onBlur={save}
          disabled={saving}
          style={{
            flex: 1,
            padding: "0.2rem 0.4rem",
            border: "1px solid var(--accent)",
            borderRadius: 4,
            fontSize: "0.85rem",
          }}
        />
      </div>
    );
  }

  return (
    <div
      onClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: "0.25rem" }}
      title="Click to edit"
    >
      <span style={{ color: "var(--text-secondary)" }}>{label}:</span>
      <strong>{value || "-"}</strong>
      <span style={{ color: "var(--text-secondary)", fontSize: "0.7rem", opacity: 0.5 }}>
        &#9998;
      </span>
    </div>
  );
}
