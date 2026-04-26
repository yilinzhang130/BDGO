"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchSharedWithMe, fetchTeamMembers, type TeamMember } from "@/lib/team";

interface SharedItem {
  share_id: number;
  item_id: number;
  entity_type: string;
  entity_key: string;
  notes?: string | null;
  owner_id: string;
  owner_name: string;
  owner_email: string;
  permission: string;
  shared_at: string;
}

const TYPE_LABELS: Record<string, string> = {
  company: "公司",
  asset: "资产",
  disease: "适应症",
  target: "靶点",
  incubator: "孵化器",
};

export default function TeamPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [shared, setShared] = useState<SharedItem[]>([]);
  const [tab, setTab] = useState<"members" | "shared">("members");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchTeamMembers(), fetchSharedWithMe()])
      .then(([m, s]) => {
        setMembers(m);
        setShared(s);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "var(--text)" }}>团队</h1>
        <Link
          href="/notifications"
          style={{ fontSize: 13, color: "var(--text-secondary)", textDecoration: "none" }}
        >
          通知 →
        </Link>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {(["members", "shared"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "7px 16px",
              borderRadius: 8,
              border: "none",
              background: tab === t ? "var(--bg-active)" : "transparent",
              color: tab === t ? "var(--accent)" : "var(--text-secondary)",
              fontWeight: tab === t ? 700 : 500,
              fontSize: 13,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            {t === "members" ? `成员 (${members.length})` : `共享的关注 (${shared.length})`}
          </button>
        ))}
      </div>

      {loading && <p style={{ color: "var(--text-muted)", fontSize: 14 }}>加载中…</p>}

      {/* Members tab */}
      {!loading && tab === "members" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
            gap: 12,
          }}
        >
          {members.length === 0 && (
            <p style={{ color: "var(--text-muted)", fontSize: 14, gridColumn: "1/-1" }}>
              暂无其他成员
            </p>
          )}
          {members.map((m) => (
            <div
              key={m.id}
              style={{
                background: "#fff",
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: "16px",
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: "50%",
                  background: "var(--bg-active)",
                  color: "var(--accent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  fontWeight: 800,
                  flexShrink: 0,
                }}
              >
                {m.name.charAt(0).toUpperCase()}
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: 14,
                    color: "var(--text)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {m.name}
                </div>
                {m.title && (
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 1 }}>
                    {m.title}
                  </div>
                )}
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    marginTop: 1,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {m.email}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Shared watchlist tab */}
      {!loading && tab === "shared" && (
        <div>
          {shared.length === 0 && (
            <div
              style={{
                textAlign: "center",
                padding: "48px 0",
                color: "var(--text-muted)",
                fontSize: 14,
              }}
            >
              没有队友分享给你的关注项
              <br />
              <span style={{ fontSize: 12, marginTop: 6, display: "block" }}>
                在关注列表页面，队友可以将关注项分享给你
              </span>
            </div>
          )}
          {shared.length > 0 && (
            <div
              style={{
                background: "#fff",
                border: "1px solid var(--border)",
                borderRadius: 12,
                overflow: "hidden",
              }}
            >
              {shared.map((item, i) => (
                <div
                  key={item.share_id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "12px 16px",
                    borderBottom: i < shared.length - 1 ? "1px solid var(--border-light)" : "none",
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      color: "var(--accent)",
                      background: "var(--bg-active)",
                      padding: "2px 7px",
                      borderRadius: 4,
                      flexShrink: 0,
                    }}
                  >
                    {TYPE_LABELS[item.entity_type] ?? item.entity_type}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
                      {item.entity_key}
                    </div>
                    {item.notes && (
                      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 1 }}>
                        {item.notes}
                      </div>
                    )}
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                      {item.owner_name}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
                      {item.permission === "edit" ? "可编辑" : "只读"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
