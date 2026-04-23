"use client";

import Link from "next/link";
import type { ConferenceAbstract, ConferenceCompanyCard } from "@/lib/api";

// ─── Helpers ──────────────────────────────────────────────────────────────────

export function cleanTitle(title: string): string {
  return title.replace(/^Abstract [A-Z0-9]+:\s*/i, "").replace(/^Abstract:\s*/i, "");
}

// ─── Badges ───────────────────────────────────────────────────────────────────

const KIND_CFG: Record<string, { bg: string; color: string; border: string }> = {
  CT: { bg: "#fef2f2", color: "#dc2626", border: "#fca5a5" },
  LB: { bg: "#fff7ed", color: "#c2410c", border: "#fdba74" },
  regular: { bg: "#f3f4f6", color: "#4b5563", border: "#d1d5db" },
};

export function KindBadge({ kind }: { kind: string }) {
  const cfg = KIND_CFG[kind] || KIND_CFG.regular;
  const label = kind === "regular" ? "Poster" : kind;
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 700,
        padding: "2px 7px",
        borderRadius: 5,
        background: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.border}`,
        letterSpacing: "0.03em",
        flexShrink: 0,
      }}
    >
      {label}
    </span>
  );
}

const TYPE_CFG: Record<string, { bg: string; color: string }> = {
  Biotech: { bg: "#eff6ff", color: "#1d4ed8" },
  "Biotech(CN)": { bg: "#f0fdf4", color: "#166534" },
  "Biotech(US)": { bg: "#eff6ff", color: "#1d4ed8" },
  "Biotech(EU)": { bg: "#faf5ff", color: "#6b21a8" },
  Pharma: { bg: "#fff7ed", color: "#9a3412" },
  "Pharma(CN)": { bg: "#f0fdf4", color: "#166534" },
  MNC: { bg: "#fefce8", color: "#854d0e" },
};

export function TypeBadge({ type }: { type?: string }) {
  if (!type) return null;
  const cfg = TYPE_CFG[type] || { bg: "#f3f4f6", color: "#6b7280" };
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: "1px 6px",
        borderRadius: 5,
        background: cfg.bg,
        color: cfg.color,
      }}
    >
      {type}
    </span>
  );
}

export function TargetTag({ label, company }: { label: string; company?: string }) {
  const style: React.CSSProperties = {
    fontSize: 11,
    padding: "2px 7px",
    borderRadius: 20,
    background: "#dbeafe",
    color: "#1e40af",
    fontWeight: 600,
    textDecoration: "none",
  };
  if (company) {
    return (
      <Link
        href={`/assets/${encodeURIComponent(company)}/${encodeURIComponent(label)}`}
        style={style}
        onClick={(e) => e.stopPropagation()}
      >
        {label}
      </Link>
    );
  }
  return <span style={style}>{label}</span>;
}

function DataTag({ label, value }: { label: string; value: string }) {
  return (
    <span
      style={{
        fontSize: 11,
        padding: "2px 7px",
        borderRadius: 20,
        background: "#f0fdf4",
        color: "#166534",
        fontWeight: 500,
      }}
    >
      {label}: <strong>{value}</strong>
    </span>
  );
}

// ─── Abstract card ─────────────────────────────────────────────────────────────

export function AbstractCard({ ab, onClick }: { ab: ConferenceAbstract; onClick: () => void }) {
  const importantDp = Object.entries(ab.data_points || {}).filter(([k]) =>
    ["ORR", "DOR", "mDOR", "mPFS", "mOS", "DCR", "N", "Gr3+AE"].includes(k),
  );

  return (
    <div
      onClick={onClick}
      style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: "18px 20px",
        cursor: "pointer",
        transition: "box-shadow 0.15s, border-color 0.15s",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)";
        (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
        (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb";
      }}
    >
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <KindBadge kind={ab.kind} />
        <h3
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 600,
            color: "#111827",
            lineHeight: 1.45,
            flex: 1,
          }}
        >
          {cleanTitle(ab.title)}
        </h3>
      </div>

      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <Link
          href={`/companies/${encodeURIComponent(ab.company)}`}
          style={{ fontSize: 12, color: "#374151", fontWeight: 600, textDecoration: "none" }}
          onClick={(e) => e.stopPropagation()}
        >
          {ab.company}
        </Link>
        <TypeBadge type={ab.客户类型} />
        {ab.所处国家 && <span style={{ fontSize: 12, color: "#9ca3af" }}>· {ab.所处国家}</span>}
      </div>

      {ab.targets?.length > 0 && (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {ab.targets.slice(0, 6).map((t) => (
            <TargetTag key={t} label={t} company={ab.company} />
          ))}
        </div>
      )}

      {importantDp.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {importantDp.map(([k, v]) => (
            <DataTag key={k} label={k} value={v} />
          ))}
        </div>
      )}

      {ab.conclusion && (
        <div
          style={{
            background: "#f9fafb",
            borderRadius: 8,
            padding: "10px 12px",
            fontSize: 12,
            color: "#374151",
            lineHeight: 1.6,
          }}
        >
          <div
            style={{
              fontWeight: 600,
              fontSize: 11,
              color: "#6b7280",
              marginBottom: 4,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Key Finding
          </div>
          {ab.conclusion}
        </div>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {ab.ncts?.map((nct) => (
          <a
            key={nct}
            href={`https://clinicaltrials.gov/study/${nct}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: "#2563eb" }}
            onClick={(e) => e.stopPropagation()}
          >
            {nct} ↗
          </a>
        ))}
        {ab.doi && (
          <a
            href={`https://doi.org/${ab.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: "#9ca3af", marginLeft: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            Abstract ↗
          </a>
        )}
      </div>
    </div>
  );
}

// ─── Company card (compact) ────────────────────────────────────────────────────

export function CompanyCard({
  card,
  onClick,
}: {
  card: ConferenceCompanyCard;
  onClick: () => void;
}) {
  const hotCount = card.CT_count + card.LB_count;
  const uniqueTargets = Array.from(
    new Set(card.top_abstracts.flatMap((a) => a.targets || [])),
  ).slice(0, 5);

  return (
    <div
      onClick={onClick}
      style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: "16px 18px",
        cursor: "pointer",
        transition: "box-shadow 0.15s, border-color 0.15s",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.08)";
        (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
        (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb";
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 10,
          alignItems: "flex-start",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#111827", marginBottom: 5 }}>
            {card.company}
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <TypeBadge type={card.客户类型} />
            {card.所处国家 && (
              <span style={{ fontSize: 11, color: "#9ca3af" }}>{card.所处国家}</span>
            )}
            {card.Ticker && <span style={{ fontSize: 11, color: "#d1d5db" }}>· {card.Ticker}</span>}
          </div>
        </div>
        {hotCount > 0 && (
          <div
            style={{
              flexShrink: 0,
              textAlign: "center",
              background: "#fef2f2",
              borderRadius: 8,
              padding: "5px 10px",
              border: "1px solid #fca5a5",
            }}
          >
            <div style={{ fontSize: 20, fontWeight: 800, color: "#dc2626", lineHeight: 1 }}>
              {hotCount}
            </div>
            <div style={{ fontSize: 9, color: "#dc2626", fontWeight: 700 }}>CT/LB</div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
        {card.CT_count > 0 && (
          <span style={{ color: "#dc2626" }}>
            <strong>{card.CT_count}</strong> CT
          </span>
        )}
        {card.LB_count > 0 && (
          <span style={{ color: "#d97706" }}>
            <strong>{card.LB_count}</strong> LB
          </span>
        )}
        <span style={{ color: "#6b7280" }}>
          <strong>{card.abstract_count}</strong> 摘要
        </span>
      </div>

      {card.top_abstracts.slice(0, 2).map((ab, i) => (
        <div
          key={i}
          style={{ fontSize: 12, color: "#4b5563", lineHeight: 1.4, display: "flex", gap: 5 }}
        >
          <KindBadge kind={ab.kind} />
          <span
            style={{
              flex: 1,
              overflow: "hidden",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
            }}
          >
            {cleanTitle(ab.title)}
          </span>
        </div>
      ))}

      {uniqueTargets.length > 0 && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {uniqueTargets.map((t) => (
            <TargetTag key={t} label={t} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Stat chip ─────────────────────────────────────────────────────────────────

export function StatChip({
  icon,
  label,
  value,
  color,
}: {
  icon: string;
  label: string;
  value?: number;
  color: string;
}) {
  if (value == null || value === 0) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <span style={{ fontSize: 14 }}>{icon}</span>
      <span style={{ fontSize: 20, fontWeight: 800, color }}>{value.toLocaleString()}</span>
      <span style={{ fontSize: 12, color: "#6b7280" }}>{label}</span>
    </div>
  );
}
