"use client";

/**
 * Reusable "coming in PR PX" stub for not-yet-built sell-side tabs.
 *
 * Each tab page (Buyers / Teaser / DD / Dataroom / Drafts) is a thin
 * shell over this until P2-3..P2-7 land. Keeps the layout / context /
 * tab nav working before the implementations ship.
 */

import { useSellAsset } from "../layout";

interface Props {
  tab: string;
  pr: string;
  what: string;
  bullets: string[];
}

export function TabComingSoon({ tab, pr, what, bullets }: Props) {
  const { asset, loading } = useSellAsset();
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E8EFFE",
        borderRadius: 12,
        padding: "32px 28px",
        boxShadow: "0 2px 12px rgba(30,58,138,0.04)",
      }}
    >
      <div style={{ fontSize: 36, marginBottom: 12 }}>🚧</div>
      <h2
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: "#0F172A",
          margin: "0 0 6px",
        }}
      >
        {tab} — 即将上线 ({pr})
      </h2>
      <p style={{ fontSize: 13, color: "#64748B", margin: "0 0 16px", lineHeight: 1.6 }}>{what}</p>
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: "#94A3B8",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: 8,
        }}
      >
        Plan
      </div>
      <ul
        style={{
          fontSize: 13,
          color: "#475569",
          margin: "0 0 20px",
          paddingLeft: 20,
          lineHeight: 1.7,
        }}
      >
        {bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
      <div
        style={{
          padding: "10px 14px",
          background: "#F8FAFC",
          borderRadius: 8,
          fontSize: 12,
          color: "#64748B",
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
        }}
      >
        Asset: {loading ? "…" : (asset?.entity_key ?? "—")} (id {asset?.id ?? "?"})
      </div>
    </div>
  );
}
