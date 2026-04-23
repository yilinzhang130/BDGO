"use client";

import Link from "next/link";
import type { ConferenceAbstract } from "@/lib/api";
import { KindBadge, TargetTag, TypeBadge, cleanTitle } from "./ConferenceCards";

/**
 * Full-screen-ish modal for a single abstract. Controlled by the parent:
 * passing `ab={null}` renders nothing.
 */
export function AbstractDetailModal({
  ab,
  onClose,
  onAsk,
}: {
  ab: ConferenceAbstract | null;
  onClose: () => void;
  onAsk: (question: string) => void;
}) {
  if (!ab) return null;

  const importantDp = Object.entries(ab.data_points || {});

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.35)",
        zIndex: 1000,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "48px 16px",
        overflowY: "auto",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 16,
          width: "100%",
          maxWidth: 680,
          padding: "28px 32px",
          position: "relative",
        }}
      >
        <button
          onClick={onClose}
          style={{
            position: "absolute",
            top: 14,
            right: 14,
            border: "none",
            background: "#f3f4f6",
            borderRadius: 6,
            width: 28,
            height: 28,
            cursor: "pointer",
            fontSize: 16,
            lineHeight: "28px",
            color: "#6b7280",
          }}
        >
          ×
        </button>

        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 12 }}>
          <KindBadge kind={ab.kind} />
          <h2
            style={{
              margin: 0,
              fontSize: 17,
              fontWeight: 700,
              color: "#111827",
              lineHeight: 1.4,
              flex: 1,
            }}
          >
            {cleanTitle(ab.title)}
          </h2>
        </div>

        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            marginBottom: 16,
            flexWrap: "wrap",
          }}
        >
          <Link
            href={`/companies/${encodeURIComponent(ab.company)}`}
            style={{ fontSize: 14, fontWeight: 600, color: "#1d4ed8", textDecoration: "none" }}
          >
            {ab.company} ↗
          </Link>
          <TypeBadge type={ab.客户类型} />
          <span style={{ fontSize: 13, color: "#9ca3af" }}>{ab.所处国家}</span>
        </div>

        {ab.targets?.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              靶点 / 资产
            </div>
            <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
              {ab.targets.map((t) => (
                <TargetTag key={t} label={t} company={ab.company} />
              ))}
            </div>
          </div>
        )}

        {importantDp.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              临床数据
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
                gap: 8,
              }}
            >
              {importantDp.map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    background: "#f9fafb",
                    borderRadius: 8,
                    padding: "10px 12px",
                    border: "1px solid #e5e7eb",
                  }}
                >
                  <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 2 }}>{k}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {ab.conclusion && (
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Key Finding
            </div>
            <div
              style={{
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: 10,
                padding: "14px 16px",
                fontSize: 13,
                color: "#14532d",
                lineHeight: 1.7,
              }}
            >
              {ab.conclusion}
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 4 }}>
          {ab.ncts?.map((nct) => (
            <a
              key={nct}
              href={`https://clinicaltrials.gov/study/${nct}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 13, color: "#2563eb", fontWeight: 500 }}
            >
              {nct} ↗
            </a>
          ))}
          {ab.doi && (
            <a
              href={`https://doi.org/${ab.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 13, color: "#6b7280" }}
            >
              原文摘要 ↗
            </a>
          )}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #f3f4f6" }}>
          <button
            onClick={() => {
              onAsk(
                `深度分析 ${ab.company} 的摘要《${cleanTitle(ab.title).slice(0, 60)}》，结合CRM数据给出BD评估`,
              );
              onClose();
            }}
            style={{
              padding: "9px 20px",
              background: "#1e3a8a",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            💬 让右侧AI分析这条摘要
          </button>
        </div>
      </div>
    </div>
  );
}
