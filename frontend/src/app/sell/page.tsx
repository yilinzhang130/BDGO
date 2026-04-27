"use client";

/**
 * Sell-side workspace home — Phase 2, P2-1.
 *
 * Lists the user's sell-side assets (sourced from watchlist entries with
 * entity_type='asset'). Each card shows:
 *   - Asset name + notes
 *   - Outreach activity (event count, last touched)
 *   - Quick action: open detail page (PR P2-2 will fill that out)
 *
 * The grid <-> list toggle is purely visual — same data both ways.
 * Empty state nudges the user toward /watchlist (the canonical add path
 * until PR P2-? wires up upload-as-asset directly).
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { fetchSellAssets, type SellAsset } from "@/lib/api";
import { errorMessage } from "@/lib/format";

type ViewMode = "grid" | "list";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

function relTime(iso: string | null): string {
  if (!iso) return "尚未外联";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "—";
  const days = Math.floor((Date.now() - d) / 86_400_000);
  if (days === 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  if (days < 30) return `${Math.floor(days / 7)} 周前`;
  if (days < 365) return `${Math.floor(days / 30)} 个月前`;
  return `${Math.floor(days / 365)} 年前`;
}

export default function SellPage() {
  const [assets, setAssets] = useState<SellAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("grid");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSellAssets({ page: 1, page_size: 100 });
      setAssets(res.data);
      setTotal(res.total);
    } catch (e: unknown) {
      setError(errorMessage(e, "加载资产失败"));
      setAssets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", padding: "32px 24px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        {/* Header */}
        <div
          style={{
            marginBottom: 24,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div>
            <h1
              style={{
                fontSize: 28,
                fontWeight: 700,
                color: "#0F172A",
                margin: "0 0 6px",
                letterSpacing: "-0.01em",
              }}
            >
              我要卖
            </h1>
            <p style={{ fontSize: 14, color: "#64748B", margin: 0 }}>
              卖方资产工作台 · 当前 {total} 个资产
            </p>
          </div>

          {/* View toggle */}
          <div
            style={{
              display: "flex",
              border: "1px solid #E2E8F0",
              borderRadius: 8,
              overflow: "hidden",
              background: "#fff",
            }}
            role="tablist"
            aria-label="View mode"
          >
            <button
              onClick={() => setView("grid")}
              role="tab"
              aria-selected={view === "grid"}
              style={viewToggleStyle(view === "grid")}
            >
              ▦ 卡片
            </button>
            <button
              onClick={() => setView("list")}
              role="tab"
              aria-selected={view === "list"}
              style={viewToggleStyle(view === "list")}
            >
              ☰ 列表
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "#FEF2F2",
              border: "1px solid #FCA5A5",
              borderRadius: 8,
              color: "#991B1B",
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        {/* Empty / loading / content */}
        {loading && assets.length === 0 ? (
          <div
            style={{
              padding: 60,
              textAlign: "center",
              color: "#94A3B8",
              background: "#fff",
              borderRadius: 12,
              border: "1px solid #E8EFFE",
            }}
          >
            加载中…
          </div>
        ) : assets.length === 0 ? (
          <EmptyState />
        ) : view === "grid" ? (
          <AssetGrid assets={assets} />
        ) : (
          <AssetList assets={assets} />
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div
      style={{
        padding: "60px 40px",
        textAlign: "center",
        background: "#fff",
        borderRadius: 12,
        border: "1px solid #E8EFFE",
        boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
      }}
    >
      <div style={{ fontSize: 48, marginBottom: 16 }}>📂</div>
      <h2
        style={{
          fontSize: 18,
          fontWeight: 600,
          color: "#0F172A",
          margin: "0 0 8px",
        }}
      >
        还没有卖方资产
      </h2>
      <p style={{ fontSize: 14, color: "#64748B", margin: "0 0 20px", lineHeight: 1.6 }}>
        把你想推介的资产加入 watchlist —— 它们会自动出现在这里。
        <br />
        未来会支持直接从 BP 上传创建。
      </p>
      <Link
        href="/watchlist"
        style={{
          display: "inline-block",
          padding: "9px 18px",
          background: "#2563EB",
          color: "#fff",
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 600,
          textDecoration: "none",
        }}
      >
        去 Watchlist 添加 →
      </Link>
    </div>
  );
}

function AssetGrid({ assets }: { assets: SellAsset[] }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 16,
      }}
    >
      {assets.map((a) => (
        <AssetCard key={a.id} asset={a} />
      ))}
    </div>
  );
}

function AssetCard({ asset }: { asset: SellAsset }) {
  return (
    <Link
      href={`/sell/${asset.id}`}
      style={{
        display: "block",
        padding: 18,
        background: "#fff",
        border: "1px solid #E8EFFE",
        borderRadius: 12,
        boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
        textDecoration: "none",
        color: "inherit",
        transition: "transform 0.12s ease, box-shadow 0.12s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 4px 16px rgba(30,58,138,0.10)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "0 2px 12px rgba(30,58,138,0.04)";
      }}
    >
      <div
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: "#0F172A",
          marginBottom: 4,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {asset.entity_key}
      </div>
      {asset.notes && (
        <div
          style={{
            fontSize: 12,
            color: "#94A3B8",
            marginBottom: 12,
            lineHeight: 1.5,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {asset.notes}
        </div>
      )}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 16,
          paddingTop: 12,
          borderTop: "1px solid #F1F5F9",
          fontSize: 11,
          color: "#64748B",
        }}
      >
        <span>📨 {asset.outreach_count} 次外联</span>
        <span>{relTime(asset.last_outreach_at)}</span>
      </div>
    </Link>
  );
}

function AssetList({ assets }: { assets: SellAsset[] }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E8EFFE",
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 120px 120px 120px",
          padding: "12px 18px",
          background: "#F8FAFC",
          borderBottom: "1px solid #E2E8F0",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          color: "#64748B",
        }}
      >
        <div>资产</div>
        <div>外联次数</div>
        <div>最近外联</div>
        <div>加入时间</div>
      </div>
      {assets.map((a) => (
        <Link
          key={a.id}
          href={`/sell/${a.id}`}
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 120px 120px 120px",
            padding: "14px 18px",
            borderBottom: "1px solid #F1F5F9",
            cursor: "pointer",
            fontSize: 13,
            color: "#0F172A",
            alignItems: "center",
            textDecoration: "none",
          }}
        >
          <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            <div style={{ fontWeight: 600 }}>{a.entity_key}</div>
            {a.notes && (
              <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>{a.notes}</div>
            )}
          </div>
          <div style={{ color: "#64748B" }}>{a.outreach_count}</div>
          <div style={{ color: "#64748B", fontSize: 12 }}>{relTime(a.last_outreach_at)}</div>
          <div style={{ color: "#94A3B8", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
            {formatDate(a.added_at)}
          </div>
        </Link>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Style helpers
// ─────────────────────────────────────────────────────────────

function viewToggleStyle(active: boolean): React.CSSProperties {
  return {
    padding: "7px 14px",
    border: "none",
    background: active ? "#2563EB" : "transparent",
    color: active ? "#fff" : "#64748B",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  };
}
