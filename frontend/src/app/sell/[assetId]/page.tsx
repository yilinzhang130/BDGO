"use client";

/**
 * Sell-side asset detail — placeholder.
 *
 * PR P2-2 turns this into the real workspace home (6 tabs: Overview /
 * Buyers / Teaser / DD / Dataroom / Drafts). For now it just renders a
 * friendly stub so the asset cards on /sell are clickable without 404ing.
 */

import Link from "next/link";
import { use } from "react";

export default function SellAssetDetailPage({ params }: { params: Promise<{ assetId: string }> }) {
  const { assetId } = use(params);
  return (
    <div style={{ minHeight: "100vh", background: "#F8FAFF", padding: "32px 24px" }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <Link
          href="/sell"
          style={{
            fontSize: 13,
            color: "#64748B",
            textDecoration: "none",
          }}
        >
          ← 我要卖
        </Link>
        <div
          style={{
            marginTop: 24,
            padding: "60px 40px",
            textAlign: "center",
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #E8EFFE",
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 16 }}>🚧</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "#0F172A", margin: "0 0 8px" }}>
            Asset detail — 即将上线
          </h1>
          <p style={{ fontSize: 14, color: "#64748B", margin: 0, lineHeight: 1.6 }}>
            资产 ID: <code>{assetId}</code>
            <br />
            下一个 PR (P2-2) 会把这里变成 6-tab 工作台： Overview · Buyers · Teaser · DD · Dataroom
            · Drafts。
          </p>
        </div>
      </div>
    </div>
  );
}
