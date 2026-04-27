"use client";

/**
 * Sell-side asset Overview tab — Phase 2, P2-2.
 *
 * Lives at /sell/[assetId] (no further segment). Reads the asset from
 * the layout context (no extra fetch). Renders three blocks:
 *   1. Quick-action row (Match buyers / Generate teaser / Discuss in chat)
 *   2. Recent outreach mini-table (last 5 events)
 *   3. Asset notes (full text)
 *
 * The tab pages for Buyers / Teaser / DD / Dataroom / Drafts are
 * sibling routes filled in by P2-3..P2-7 in parallel.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSellAsset } from "./layout";

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  sent: { bg: "#DBEAFE", color: "#1E40AF", label: "Sent" },
  replied: { bg: "#DCFCE7", color: "#166534", label: "Replied" },
  meeting: { bg: "#FEF3C7", color: "#92400E", label: "Meeting" },
  cda_signed: { bg: "#E0E7FF", color: "#3730A3", label: "CDA" },
  ts_signed: { bg: "#FCE7F3", color: "#9F1239", label: "TS" },
  definitive_signed: { bg: "#D1FAE5", color: "#065F46", label: "Closed" },
  passed: { bg: "#F3F4F6", color: "#4B5563", label: "Pass" },
  dead: { bg: "#FEE2E2", color: "#991B1B", label: "Dead" },
};

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

export default function SellAssetOverviewPage() {
  const router = useRouter();
  const { asset, loading } = useSellAsset();

  if (loading && !asset) {
    return <PanelMessage>加载中…</PanelMessage>;
  }
  if (!asset) {
    return <PanelMessage>无法加载资产数据。</PanelMessage>;
  }

  const recent = asset.recent_outreach ?? [];
  const baseHref = `/sell/${asset.id}`;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Quick actions */}
      <Panel>
        <SectionHeader>下一步动作</SectionHeader>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link href={`${baseHref}/buyers`} style={primaryActionStyle}>
            🎯 Match buyers
          </Link>
          <Link href={`${baseHref}/teaser`} style={secondaryActionStyle}>
            📝 Generate teaser
          </Link>
          <Link href={`${baseHref}/dd`} style={secondaryActionStyle}>
            📋 DD 准备
          </Link>
          <Link href={`${baseHref}/dataroom`} style={secondaryActionStyle}>
            📂 Data room
          </Link>
          <Link href={`${baseHref}/drafts`} style={secondaryActionStyle}>
            ✍️ 起草协议
          </Link>
          <button
            onClick={() =>
              router.push(
                `/chat?context=asset&asset_id=${asset.id}&asset_key=${encodeURIComponent(
                  asset.entity_key,
                )}`,
              )
            }
            style={ghostActionStyle}
          >
            💬 在 chat 里讨论
          </button>
        </div>
      </Panel>

      {/* Recent outreach */}
      <Panel>
        <SectionHeader>
          最近外联
          <Link
            href={`/outreach?search=${encodeURIComponent(asset.entity_key)}`}
            style={{ fontSize: 12, color: "#2563EB", textDecoration: "none", fontWeight: 500 }}
          >
            查看全部 →
          </Link>
        </SectionHeader>
        {recent.length === 0 ? (
          <div style={{ padding: "24px 0", color: "#94A3B8", fontSize: 13, textAlign: "center" }}>
            还没有外联记录。点上方 “Match buyers” 找潜在买方，或在{" "}
            <Link href="/outreach" style={{ color: "#2563EB", textDecoration: "none" }}>
              /outreach
            </Link>{" "}
            手工 log 一条。
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "100px 1fr 1fr 100px",
              fontSize: 13,
              border: "1px solid #F1F5F9",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            <Cell header>日期</Cell>
            <Cell header>对手</Cell>
            <Cell header>主题</Cell>
            <Cell header>状态</Cell>
            {recent.map((r) => {
              const badge = STATUS_BADGE[r.status] || {
                bg: "#F3F4F6",
                color: "#4B5563",
                label: r.status,
              };
              return (
                <SectionRow
                  key={r.id}
                  date={formatDate(r.created_at)}
                  company={r.to_company}
                  contact={r.to_contact}
                  subject={r.subject}
                  badge={badge}
                />
              );
            })}
          </div>
        )}
      </Panel>

      {/* Asset notes */}
      {asset.notes && (
        <Panel>
          <SectionHeader>资产备注</SectionHeader>
          <div
            style={{
              fontSize: 13,
              color: "#0F172A",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
            }}
          >
            {asset.notes}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Local building blocks
// ─────────────────────────────────────────────────────────────

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E8EFFE",
        borderRadius: 12,
        padding: "18px 20px",
        boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
      }}
    >
      {children}
    </div>
  );
}

function PanelMessage({ children }: { children: React.ReactNode }) {
  return (
    <Panel>
      <div style={{ padding: "20px 0", color: "#94A3B8", fontSize: 14, textAlign: "center" }}>
        {children}
      </div>
    </Panel>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        fontSize: 12,
        fontWeight: 700,
        color: "#64748B",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        marginBottom: 12,
      }}
    >
      {children}
    </div>
  );
}

function Cell({ children, header }: { children: React.ReactNode; header?: boolean }) {
  return (
    <div
      style={{
        padding: "10px 12px",
        background: header ? "#F8FAFC" : "transparent",
        borderBottom: "1px solid #F1F5F9",
        fontSize: header ? 11 : 13,
        fontWeight: header ? 700 : 400,
        color: header ? "#64748B" : "#0F172A",
        letterSpacing: header ? "0.05em" : 0,
        textTransform: header ? "uppercase" : "none",
      }}
    >
      {children}
    </div>
  );
}

function SectionRow({
  date,
  company,
  contact,
  subject,
  badge,
}: {
  date: string;
  company: string;
  contact: string | null;
  subject: string | null;
  badge: { bg: string; color: string; label: string };
}) {
  return (
    <>
      <Cell>
        <span style={{ color: "#64748B", fontVariantNumeric: "tabular-nums" }}>{date}</span>
      </Cell>
      <Cell>
        <div style={{ fontWeight: 600 }}>{company}</div>
        {contact && <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>{contact}</div>}
      </Cell>
      <Cell>
        <div
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: subject ? "#0F172A" : "#CBD5E1",
          }}
        >
          {subject || "—"}
        </div>
      </Cell>
      <Cell>
        <span
          style={{
            display: "inline-block",
            padding: "2px 9px",
            borderRadius: 10,
            background: badge.bg,
            color: badge.color,
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          {badge.label}
        </span>
      </Cell>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// Action button styles
// ─────────────────────────────────────────────────────────────

const baseActionStyle: React.CSSProperties = {
  padding: "9px 16px",
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  textDecoration: "none",
  cursor: "pointer",
  border: "1px solid transparent",
  display: "inline-block",
};

const primaryActionStyle: React.CSSProperties = {
  ...baseActionStyle,
  background: "#2563EB",
  color: "#fff",
};

const secondaryActionStyle: React.CSSProperties = {
  ...baseActionStyle,
  background: "#fff",
  color: "#0F172A",
  border: "1px solid #E2E8F0",
};

const ghostActionStyle: React.CSSProperties = {
  ...baseActionStyle,
  background: "transparent",
  color: "#64748B",
  border: "1px solid #E2E8F0",
};
