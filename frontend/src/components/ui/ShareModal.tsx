"use client";

/**
 * ShareModal  (P3-14)
 *
 * Generic teammate-picker modal.  Used for:
 *   - Sharing a watchlist item:   mode="watchlist", itemId={number}
 *   - Notifying about a report:   mode="report",    taskId={string}
 *
 * Searches teammates by name/email, shows permission picker for watchlist mode,
 * optional note, and submits via the team API client.
 */

import { useEffect, useRef, useState } from "react";
import {
  fetchTeamMembers,
  notifyTeammateAboutReport,
  shareWatchlistItem,
  type TeamMember,
} from "@/lib/team";

interface Props {
  mode: "watchlist" | "report";
  itemId?: number; // watchlist item id
  taskId?: string; // report task id
  onClose: () => void;
  onSuccess?: () => void;
}

export function ShareModal({ mode, itemId, taskId, onClose, onSuccess }: Props) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<TeamMember | null>(null);
  const [permission, setPermission] = useState<"view" | "edit">("view");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchTeamMembers()
      .then(setMembers)
      .catch(() => {});
    setTimeout(() => inputRef.current?.focus(), 50);
  }, []);

  const filtered = members.filter((m) => {
    const q = search.toLowerCase();
    return m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q);
  });

  const handleSubmit = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError("");
    try {
      if (mode === "watchlist" && itemId !== undefined) {
        await shareWatchlistItem(itemId, selected.id, permission, note || undefined);
      } else if (mode === "report" && taskId) {
        await notifyTeammateAboutReport(taskId, selected.id, note || undefined);
      }
      setDone(true);
      onSuccess?.();
      setTimeout(onClose, 1200);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "操作失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(15,23,42,0.35)",
          zIndex: 800,
        }}
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={mode === "watchlist" ? "分享关注项" : "通知队友"}
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          zIndex: 801,
          background: "#fff",
          borderRadius: 16,
          padding: "28px 28px 24px",
          width: 400,
          maxWidth: "calc(100vw - 32px)",
          boxShadow: "0 24px 64px rgba(15,23,42,0.18)",
          fontFamily: "inherit",
        }}
      >
        <h2 style={{ margin: "0 0 20px", fontSize: 16, fontWeight: 800, color: "var(--text)" }}>
          {mode === "watchlist" ? "分享关注项" : "通知队友"}
        </h2>

        {done ? (
          <div
            style={{ textAlign: "center", padding: "16px 0", color: "#059669", fontWeight: 600 }}
          >
            ✓ 已发送通知
          </div>
        ) : (
          <>
            {/* Search */}
            <div style={{ marginBottom: 12 }}>
              <input
                ref={inputRef}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索队友姓名或邮箱…"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  fontSize: 13,
                  outline: "none",
                  boxSizing: "border-box",
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Member list */}
            <div
              style={{
                border: "1px solid var(--border)",
                borderRadius: 8,
                maxHeight: 180,
                overflowY: "auto",
                marginBottom: 14,
              }}
            >
              {filtered.length === 0 && (
                <div
                  style={{
                    padding: "16px",
                    textAlign: "center",
                    color: "var(--text-muted)",
                    fontSize: 12,
                  }}
                >
                  暂无队友
                </div>
              )}
              {filtered.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setSelected(m)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    width: "100%",
                    padding: "9px 12px",
                    background: selected?.id === m.id ? "var(--bg-active)" : "transparent",
                    border: "none",
                    borderBottom: "1px solid var(--border-light)",
                    cursor: "pointer",
                    textAlign: "left",
                    fontFamily: "inherit",
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: "var(--bg-active)",
                      color: "var(--accent)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    {m.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                      {m.name}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{m.email}</div>
                  </div>
                  {selected?.id === m.id && (
                    <span style={{ marginLeft: "auto", color: "var(--accent)", fontSize: 14 }}>
                      ✓
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Permission (watchlist only) */}
            {mode === "watchlist" && (
              <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                {(["view", "edit"] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPermission(p)}
                    style={{
                      flex: 1,
                      padding: "7px",
                      borderRadius: 8,
                      border: `1.5px solid ${permission === p ? "var(--accent)" : "var(--border)"}`,
                      background: permission === p ? "var(--bg-active)" : "#fff",
                      color: permission === p ? "var(--accent)" : "var(--text-secondary)",
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    {p === "view" ? "只读" : "可编辑"}
                  </button>
                ))}
              </div>
            )}

            {/* Note */}
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="附言（可选）"
              rows={2}
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                resize: "none",
                fontFamily: "inherit",
                boxSizing: "border-box",
                marginBottom: 16,
              }}
            />

            {error && (
              <p style={{ fontSize: 12, color: "var(--red)", marginBottom: 12 }}>{error}</p>
            )}

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                onClick={onClose}
                style={{
                  padding: "8px 18px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "#fff",
                  fontSize: 13,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={!selected || submitting}
                style={{
                  padding: "8px 18px",
                  borderRadius: 8,
                  border: "none",
                  background: selected && !submitting ? "var(--accent)" : "var(--border)",
                  color: selected && !submitting ? "#fff" : "var(--text-muted)",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: selected && !submitting ? "pointer" : "not-allowed",
                  fontFamily: "inherit",
                }}
              >
                {submitting ? "发送中…" : "发送"}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
