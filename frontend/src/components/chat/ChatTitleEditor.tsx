"use client";

import { useState } from "react";

/** Inline title display + click-to-edit with enter/escape keyboard handling. */
export function ChatTitleEditor({
  title,
  onRename,
}: {
  title: string;
  onRename: (next: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);

  const start = () => {
    setDraft(title);
    setEditing(true);
  };

  const save = () => {
    const next = draft.trim();
    if (next) onRename(next);
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
          if (e.key === "Escape") setEditing(false);
        }}
        className="chat-header-title"
        style={{ borderBottom: "1px solid var(--accent)" }}
      />
    );
  }

  return (
    <div
      className="chat-header-title"
      onClick={start}
      title="Click to rename"
      style={{ cursor: "pointer" }}
    >
      {title}
    </div>
  );
}
