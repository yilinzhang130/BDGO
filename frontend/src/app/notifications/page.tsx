"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from "@/lib/team";

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchNotifications({ limit: 50 });
      setItems(data.items);
      setUnread(data.unread);
    } catch {
      setError("加载通知失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRead = async (id: number) => {
    await markNotificationRead(id);
    setItems((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)),
    );
    setUnread((c) => Math.max(0, c - 1));
  };

  const handleReadAll = async () => {
    await markAllNotificationsRead();
    setItems((prev) => prev.map((n) => ({ ...n, read_at: new Date().toISOString() })));
    setUnread(0);
  };

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "var(--text)" }}>
          通知
          {unread > 0 && (
            <span
              style={{
                marginLeft: 10,
                fontSize: 12,
                background: "#DC2626",
                color: "#fff",
                borderRadius: 10,
                padding: "2px 7px",
                fontWeight: 700,
              }}
            >
              {unread} 未读
            </span>
          )}
        </h1>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {unread > 0 && (
            <button
              onClick={handleReadAll}
              style={{
                fontSize: 13,
                color: "var(--accent)",
                background: "none",
                border: "none",
                cursor: "pointer",
                fontWeight: 600,
                fontFamily: "inherit",
              }}
            >
              全部标已读
            </button>
          )}
          <Link
            href="/team"
            style={{ fontSize: 13, color: "var(--text-secondary)", textDecoration: "none" }}
          >
            团队成员 →
          </Link>
        </div>
      </div>

      {/* Content */}
      {loading && <p style={{ color: "var(--text-muted)", fontSize: 14 }}>加载中…</p>}
      {error && <p style={{ color: "var(--red)", fontSize: 14 }}>{error}</p>}
      {!loading && !error && items.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "60px 0",
            color: "var(--text-muted)",
            fontSize: 14,
          }}
        >
          暂无通知
        </div>
      )}

      {!loading && items.length > 0 && (
        <div
          style={{
            background: "#fff",
            border: "1px solid var(--border)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          {items.map((n, i) => (
            <NotifItem
              key={n.id}
              notif={n}
              isLast={i === items.length - 1}
              onRead={() => handleRead(n.id)}
            />
          ))}
        </div>
      )}
    </main>
  );
}

function NotifItem({
  notif,
  isLast,
  onRead,
}: {
  notif: Notification;
  isLast: boolean;
  onRead: () => void;
}) {
  const isUnread = !notif.read_at;
  const typeLabel: Record<string, string> = {
    watchlist_share: "关注分享",
    report_share: "报告分享",
    mention: "提及",
  };

  const row = (
    <div
      onClick={() => {
        if (isUnread) onRead();
      }}
      style={{
        display: "flex",
        gap: 14,
        padding: "14px 18px",
        background: isUnread ? "#f8faff" : "#fff",
        borderBottom: isLast ? "none" : "1px solid var(--border-light)",
        cursor: notif.link_url ? "pointer" : "default",
        transition: "background 0.1s",
      }}
    >
      {/* Dot */}
      <div style={{ paddingTop: 4, flexShrink: 0 }}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: isUnread ? "var(--accent)" : "var(--border)",
          }}
        />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Type badge + sender */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "var(--accent)",
              background: "var(--bg-active)",
              padding: "1px 6px",
              borderRadius: 4,
            }}
          >
            {typeLabel[notif.type] ?? notif.type}
          </span>
          {notif.sender_name && (
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              {notif.sender_name}
            </span>
          )}
        </div>

        <div
          style={{
            fontSize: 14,
            fontWeight: isUnread ? 700 : 500,
            color: "var(--text)",
            marginBottom: 3,
          }}
        >
          {notif.title}
        </div>

        {notif.body && (
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
            {notif.body}
          </div>
        )}

        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
          {new Date(notif.created_at).toLocaleString("zh-CN")}
        </div>
      </div>
    </div>
  );

  if (notif.link_url) {
    return (
      <Link href={notif.link_url} style={{ textDecoration: "none" }}>
        {row}
      </Link>
    );
  }
  return row;
}
