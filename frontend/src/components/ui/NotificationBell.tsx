"use client";

/**
 * NotificationBell  (P3-14)
 *
 * Shows a bell icon with an unread badge in the sidebar footer.
 * Clicking opens a dropdown with the latest 10 notifications.
 * Polling every 60s keeps the count fresh without SSE infra.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchNotificationUnreadCount,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from "@/lib/team";
import { useAuth } from "@/components/AuthProvider";

const POLL_MS = 60_000;

export function NotificationBell() {
  const { user } = useAuth();
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(async () => {
    if (!user) return;
    try {
      const n = await fetchNotificationUnreadCount();
      setCount(n);
    } catch {
      /* silent */
    }
  }, [user]);

  // Poll for unread count
  useEffect(() => {
    refreshCount();
    const id = setInterval(refreshCount, POLL_MS);
    return () => clearInterval(id);
  }, [refreshCount]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleOpen = async () => {
    setOpen((v) => !v);
    if (!open) {
      setLoading(true);
      try {
        const data = await fetchNotifications({ limit: 10 });
        setItems(data.items);
        setCount(data.unread);
      } catch {
        /* silent */
      } finally {
        setLoading(false);
      }
    }
  };

  const handleMarkRead = async (id: number) => {
    await markNotificationRead(id);
    setItems((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)),
    );
    setCount((c) => Math.max(0, c - 1));
  };

  const handleMarkAll = async () => {
    await markAllNotificationsRead();
    setItems((prev) => prev.map((n) => ({ ...n, read_at: new Date().toISOString() })));
    setCount(0);
  };

  if (!user) return null;

  return (
    <div style={{ position: "relative" }} ref={dropRef}>
      <button
        onClick={handleOpen}
        title="通知"
        style={{
          position: "relative",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "6px",
          borderRadius: 8,
          color: "var(--text-secondary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Bell icon */}
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        >
          <path d="M8 1.5a5 5 0 0 1 5 5v2.5l1.5 2H1.5L3 9V6.5a5 5 0 0 1 5-5z" />
          <path d="M6.5 13.5a1.5 1.5 0 0 0 3 0" />
        </svg>
        {count > 0 && (
          <span
            style={{
              position: "absolute",
              top: 2,
              right: 2,
              minWidth: 14,
              height: 14,
              background: "#DC2626",
              color: "#fff",
              fontSize: 9,
              fontWeight: 700,
              borderRadius: 7,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 3px",
              lineHeight: 1,
            }}
          >
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: 0,
            width: 300,
            background: "#fff",
            border: "1px solid var(--border)",
            borderRadius: 12,
            boxShadow: "var(--shadow-lg)",
            zIndex: 500,
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              borderBottom: "1px solid var(--border-light)",
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>通知</span>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {count > 0 && (
                <button
                  onClick={handleMarkAll}
                  style={{
                    fontSize: 11,
                    color: "var(--accent)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                  }}
                >
                  全部标已读
                </button>
              )}
              <Link
                href="/notifications"
                onClick={() => setOpen(false)}
                style={{ fontSize: 11, color: "var(--text-muted)", textDecoration: "none" }}
              >
                查看全部 →
              </Link>
            </div>
          </div>

          {/* Body */}
          <div style={{ maxHeight: 320, overflowY: "auto" }}>
            {loading && (
              <div
                style={{
                  padding: "20px",
                  textAlign: "center",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                加载中…
              </div>
            )}
            {!loading && items.length === 0 && (
              <div
                style={{
                  padding: "20px",
                  textAlign: "center",
                  color: "var(--text-muted)",
                  fontSize: 13,
                }}
              >
                暂无通知
              </div>
            )}
            {!loading &&
              items.map((n) => (
                <NotifRow
                  key={n.id}
                  notif={n}
                  onRead={() => handleMarkRead(n.id)}
                  onClose={() => setOpen(false)}
                />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function NotifRow({
  notif,
  onRead,
  onClose,
}: {
  notif: Notification;
  onRead: () => void;
  onClose: () => void;
}) {
  const isUnread = !notif.read_at;
  const content = (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "10px 14px",
        background: isUnread ? "#f8faff" : "#fff",
        borderBottom: "1px solid var(--border-light)",
        cursor: notif.link_url ? "pointer" : "default",
        transition: "background 0.1s",
      }}
      onClick={() => {
        if (isUnread) onRead();
      }}
    >
      <div
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: isUnread ? "#1E3A8A" : "transparent",
          flexShrink: 0,
          marginTop: 5,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: isUnread ? 600 : 400,
            color: "var(--text)",
            lineHeight: 1.4,
          }}
        >
          {notif.title}
        </div>
        {notif.body && (
          <div
            style={{
              fontSize: 11,
              color: "var(--text-secondary)",
              marginTop: 2,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {notif.body}
          </div>
        )}
        <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 3 }}>
          {new Date(notif.created_at).toLocaleString("zh-CN", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );

  if (notif.link_url) {
    return (
      <Link href={notif.link_url} style={{ textDecoration: "none" }} onClick={onClose}>
        {content}
      </Link>
    );
  }
  return content;
}
