"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useSessionStore } from "@/lib/sessions";

export function SessionList() {
  const router = useRouter();
  const pathname = usePathname();
  const { sessions, activeId, setActiveId, deleteSession, renameSession } = useSessionStore();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");

  if (sessions.length === 0) {
    return <div className="session-empty">No chats yet. Click + New Chat.</div>;
  }

  const handleClick = (id: string) => {
    if (editingId === id) return;
    setActiveId(id);
    if (pathname !== "/chat") router.push("/chat");
  };

  const startRename = (e: React.MouseEvent, id: string, currentTitle: string) => {
    e.stopPropagation();
    setEditingId(id);
    setDraftTitle(currentTitle);
  };

  const saveRename = () => {
    if (editingId) {
      renameSession(editingId, draftTitle);
      setEditingId(null);
    }
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm("Delete this chat?")) {
      deleteSession(id);
    }
  };

  return (
    <>
      {sessions.map((s) => {
        const isActive = s.id === activeId && pathname === "/chat";
        const isEditing = editingId === s.id;
        return (
          <div
            key={s.id}
            className={`session-item ${isActive ? "active" : ""}`}
            onClick={() => handleClick(s.id)}
            title={s.title}
          >
            {isEditing ? (
              <input
                autoFocus
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                onBlur={saveRename}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveRename();
                  if (e.key === "Escape") setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
                style={{
                  flex: 1,
                  border: "1px solid var(--accent)",
                  borderRadius: 4,
                  padding: "0.15rem 0.35rem",
                  fontSize: "0.8rem",
                  background: "var(--bg-card)",
                  color: "var(--text)",
                  outline: "none",
                }}
              />
            ) : (
              <>
                <span className="session-item-title">{s.title}</span>
                <div className="session-item-actions">
                  <button
                    className="session-item-btn"
                    onClick={(e) => startRename(e, s.id, s.title)}
                    title="Rename"
                  >
                    {"\u270E"}
                  </button>
                  <button
                    className="session-item-btn"
                    onClick={(e) => handleDelete(e, s.id)}
                    title="Delete"
                  >
                    {"\u2715"}
                  </button>
                </div>
              </>
            )}
          </div>
        );
      })}
    </>
  );
}
