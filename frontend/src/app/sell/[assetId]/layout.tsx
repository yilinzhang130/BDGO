"use client";

/**
 * Sell-side asset detail layout — Phase 2, P2-2.
 *
 * Wraps every /sell/[assetId]/* route with:
 *   - Back link to /sell
 *   - Asset header (name, notes, outreach badge)
 *   - 6-tab nav: Overview / Buyers / Teaser / DD / Dataroom / Drafts
 *
 * The fetched asset is provided to children via the SellAssetContext
 * so the per-tab pages don't need to refetch on every nav. Tabs PR
 * P2-3..P2-7 each implement their own tab page; for now they are
 * "Coming soon" stubs so the nav doesn't 404.
 */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { fetchSellAsset, type SellAssetDetail } from "@/lib/api";
import { errorMessage } from "@/lib/format";

// ─────────────────────────────────────────────────────────────
// Tab definitions (single source of truth — also drives stubs)
// ─────────────────────────────────────────────────────────────

interface TabDef {
  slug: string; // route segment ("" = Overview at /sell/[id])
  label: string;
  hint: string; // tooltip / future-PR label
}

export const SELL_TABS: TabDef[] = [
  { slug: "", label: "Overview", hint: "资产关键字段 + 最近外联" },
  { slug: "buyers", label: "Buyers", hint: "反向匹配买方 (P2-3)" },
  { slug: "teaser", label: "Teaser", hint: "生成 + 按买方定制 (P2-4)" },
  { slug: "dd", label: "DD", hint: "DD checklist + 会议 + FAQ (P2-5)" },
  { slug: "dataroom", label: "Dataroom", hint: "数据室清单 (P2-6)" },
  { slug: "drafts", label: "Drafts", hint: "TS / MTA / License / Co-Dev / SPA (P2-7)" },
];

// ─────────────────────────────────────────────────────────────
// Context: child pages read the asset from here, no refetch
// ─────────────────────────────────────────────────────────────

interface SellAssetContextValue {
  asset: SellAssetDetail | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const SellAssetContext = createContext<SellAssetContextValue | null>(null);

export function useSellAsset(): SellAssetContextValue {
  const ctx = useContext(SellAssetContext);
  if (!ctx) {
    throw new Error("useSellAsset must be used inside the /sell/[assetId] layout");
  }
  return ctx;
}

// ─────────────────────────────────────────────────────────────
// Layout component
// ─────────────────────────────────────────────────────────────

export default function SellAssetLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ assetId: string }>();
  const assetId = params?.assetId ?? "";
  const pathname = usePathname();

  const [asset, setAsset] = useState<SellAssetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!assetId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSellAsset(assetId);
      setAsset(res);
    } catch (e: unknown) {
      setError(errorMessage(e, "加载资产失败"));
      setAsset(null);
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Determine which tab is active. Pathname looks like
  //   /sell/123              -> "" (Overview)
  //   /sell/123/buyers       -> "buyers"
  // We match the trailing segment after the asset id.
  const baseHref = `/sell/${assetId}`;
  const trailing = pathname?.startsWith(baseHref) ? pathname.slice(baseHref.length) : "";
  const activeSlug = trailing.replace(/^\//, "").split("/")[0] ?? "";

  return (
    <SellAssetContext.Provider value={{ asset, loading, error, reload: load }}>
      <div style={{ minHeight: "100vh", background: "#F8FAFF" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", padding: "24px 24px 0" }}>
          {/* Back */}
          <Link
            href="/sell"
            style={{
              fontSize: 13,
              color: "#64748B",
              textDecoration: "none",
              display: "inline-block",
              marginBottom: 16,
            }}
          >
            ← 我要卖
          </Link>

          {/* Asset header card */}
          <div
            style={{
              background: "#fff",
              border: "1px solid #E8EFFE",
              borderRadius: 12,
              padding: "20px 24px",
              marginBottom: 0,
              boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
              borderBottomLeftRadius: 0,
              borderBottomRightRadius: 0,
            }}
          >
            {error && (
              <div
                style={{
                  padding: "10px 14px",
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

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: 16,
                flexWrap: "wrap",
              }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: "#94A3B8",
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Sell-side Asset
                </div>
                <h1
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: "#0F172A",
                    margin: "0 0 6px",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {loading && !asset ? "加载中…" : asset?.entity_key || "—"}
                </h1>
                {asset?.notes && (
                  <p style={{ fontSize: 13, color: "#64748B", margin: 0, lineHeight: 1.55 }}>
                    {asset.notes}
                  </p>
                )}
              </div>

              {asset && (
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    fontSize: 12,
                    color: "#64748B",
                    flexShrink: 0,
                  }}
                >
                  <Stat label="外联次数" value={String(asset.outreach_count)} />
                  <Stat
                    label="加入时间"
                    value={
                      asset.added_at ? new Date(asset.added_at).toISOString().slice(0, 10) : "—"
                    }
                  />
                </div>
              )}
            </div>
          </div>

          {/* Tab nav */}
          <nav
            role="tablist"
            aria-label="Asset workspace tabs"
            style={{
              display: "flex",
              gap: 0,
              background: "#fff",
              border: "1px solid #E8EFFE",
              borderTop: "none",
              borderBottomLeftRadius: 12,
              borderBottomRightRadius: 12,
              boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
              marginBottom: 24,
              overflowX: "auto",
            }}
          >
            {SELL_TABS.map((tab) => {
              const href = tab.slug ? `${baseHref}/${tab.slug}` : baseHref;
              const active = activeSlug === tab.slug;
              return (
                <Link
                  key={tab.slug || "overview"}
                  href={href}
                  role="tab"
                  aria-selected={active}
                  title={tab.hint}
                  style={{
                    padding: "12px 18px",
                    fontSize: 13,
                    fontWeight: active ? 700 : 500,
                    color: active ? "#2563EB" : "#64748B",
                    borderBottom: active ? "2px solid #2563EB" : "2px solid transparent",
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Tab content */}
        <div style={{ maxWidth: 1180, margin: "0 auto", padding: "0 24px 60px" }}>{children}</div>
      </div>
    </SellAssetContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ textAlign: "right" }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: "#94A3B8",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: "#0F172A",
          marginTop: 2,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
    </div>
  );
}
