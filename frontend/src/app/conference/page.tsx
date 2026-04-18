"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  fetchConferenceSessions,
  fetchConferenceStats,
  fetchConferenceCompanies,
  ConferenceSession,
  ConferenceCompanyCard,
  ConferenceListResponse,
} from "@/lib/api";

// ─── Type badge ────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, { bg: string; color: string }> = {
  "Biotech":     { bg: "#eff6ff", color: "#1d4ed8" },
  "Biotech(CN)": { bg: "#f0fdf4", color: "#166534" },
  "Biotech(US)": { bg: "#eff6ff", color: "#1d4ed8" },
  "Biotech(EU)": { bg: "#faf5ff", color: "#6b21a8" },
  "Pharma":      { bg: "#fff7ed", color: "#9a3412" },
  "Pharma(CN)":  { bg: "#f0fdf4", color: "#166534" },
  "MNC":         { bg: "#fefce8", color: "#854d0e" },
  "学术/医院":   { bg: "#f9fafb", color: "#4b5563" },
  "Other":       { bg: "#f9fafb", color: "#4b5563" },
};

function TypeBadge({ type }: { type?: string }) {
  const t = type || "Other";
  const cfg = TYPE_COLORS[t] || { bg: "#f3f4f6", color: "#6b7280" };
  return (
    <span style={{
      display: "inline-block", padding: "1px 7px", borderRadius: 6, fontSize: 11,
      fontWeight: 600, background: cfg.bg, color: cfg.color,
    }}>{t}</span>
  );
}

// ─── Kind badge ────────────────────────────────────────────────────────────────

function KindBadge({ kind }: { kind: string }) {
  const isHot = kind === "CT" || kind === "LB";
  return (
    <span style={{
      display: "inline-block", padding: "0px 5px", borderRadius: 4, fontSize: 10,
      fontWeight: 700, letterSpacing: "0.02em",
      background: isHot ? "#fef2f2" : "#f3f4f6",
      color: isHot ? "#dc2626" : "#6b7280",
      border: isHot ? "1px solid #fca5a5" : "1px solid #e5e7eb",
    }}>{kind}</span>
  );
}

// ─── Company flash card ────────────────────────────────────────────────────────

function CompanyCard({
  card,
  sessionId,
  onClick,
}: {
  card: ConferenceCompanyCard;
  sessionId: string;
  onClick: () => void;
}) {
  const hotCount = card.CT_count + card.LB_count;
  return (
    <div
      onClick={onClick}
      style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: "16px",
        cursor: "pointer",
        transition: "box-shadow 0.15s, border-color 0.15s",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.08)";
        (e.currentTarget as HTMLDivElement).style.borderColor = "#93c5fd";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
        (e.currentTarget as HTMLDivElement).style.borderColor = "#e5e7eb";
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#111827", lineHeight: 1.3, marginBottom: 4 }}>
            {card.company}
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <TypeBadge type={card.客户类型} />
            {card.所处国家 && (
              <span style={{ fontSize: 11, color: "#6b7280" }}>{card.所处国家}</span>
            )}
          </div>
        </div>
        {/* CT/LB hot count */}
        {hotCount > 0 && (
          <div style={{
            flexShrink: 0, textAlign: "center",
            background: "#fef2f2", borderRadius: 8,
            padding: "4px 10px", border: "1px solid #fca5a5",
          }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#dc2626", lineHeight: 1 }}>{hotCount}</div>
            <div style={{ fontSize: 9, color: "#dc2626", fontWeight: 600, marginTop: 1 }}>CT/LB</div>
          </div>
        )}
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#6b7280" }}>
        <span>
          <span style={{ fontWeight: 600, color: "#374151" }}>{card.CT_count}</span> CT
        </span>
        <span>
          <span style={{ fontWeight: 600, color: "#374151" }}>{card.LB_count}</span> LB
        </span>
        <span>
          <span style={{ fontWeight: 600, color: "#374151" }}>{card.abstract_count}</span> 总计
        </span>
        {card.Ticker && (
          <span style={{ marginLeft: "auto", color: "#9ca3af", fontSize: 11 }}>{card.Ticker}</span>
        )}
      </div>

      {/* Top abstracts */}
      {card.top_abstracts.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {card.top_abstracts.map((ab, i) => (
            <div key={i} style={{
              fontSize: 11, color: "#4b5563", lineHeight: 1.4,
              display: "flex", gap: 5, alignItems: "flex-start",
            }}>
              <KindBadge kind={ab.kind} />
              <span style={{
                flex: 1,
                overflow: "hidden",
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
              }}>
                {ab.title.replace(/^Abstract [A-Z0-9]+:\s*/i, "")}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Targets */}
      {card.top_abstracts.some(a => a.targets?.length > 0) && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {Array.from(new Set(card.top_abstracts.flatMap(a => a.targets || []))).slice(0, 5).map(t => (
            <span key={t} style={{
              fontSize: 10, padding: "1px 5px", borderRadius: 4,
              background: "#f3f4f6", color: "#374151", fontWeight: 500,
            }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Company detail modal ──────────────────────────────────────────────────────

function CompanyDetailModal({
  company,
  data,
  onClose,
}: {
  company: string;
  data: any;
  onClose: () => void;
}) {
  if (!data) return null;

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        zIndex: 1000, display: "flex", alignItems: "flex-start", justifyContent: "center",
        padding: "40px 16px", overflowY: "auto",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: "#fff", borderRadius: 16, width: "100%", maxWidth: 720,
        padding: "28px 32px", position: "relative",
      }}>
        {/* Close */}
        <button
          onClick={onClose}
          style={{
            position: "absolute", top: 16, right: 16,
            border: "none", background: "#f3f4f6", borderRadius: 6,
            width: 28, height: 28, cursor: "pointer", fontSize: 16, lineHeight: "28px",
            color: "#6b7280",
          }}
        >×</button>

        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#111827" }}>{data.company}</h2>
          <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
            <TypeBadge type={data.客户类型} />
            {data.所处国家 && <span style={{ fontSize: 13, color: "#6b7280" }}>{data.所处国家}</span>}
            {data.Ticker && <span style={{ fontSize: 12, color: "#9ca3af" }}>{data.Ticker}</span>}
            {data["市值/估值"] && <span style={{ fontSize: 12, color: "#6b7280" }}>{data["市值/估值"]}</span>}
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 13 }}>
            <span><strong style={{ color: "#dc2626" }}>{data.CT_count}</strong> CT abstracts</span>
            <span><strong style={{ color: "#d97706" }}>{data.LB_count}</strong> Late-Breaking</span>
            <span><strong>{(data.abstracts || []).length}</strong> 总计</span>
          </div>
        </div>

        {/* Abstracts */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {(data.abstracts || []).map((ab: any, i: number) => (
            <div key={i} style={{
              border: "1px solid #e5e7eb", borderRadius: 10, padding: "14px 16px",
              background: ab.kind === "CT" || ab.kind === "LB" ? "#fffbeb" : "#fafafa",
            }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 6 }}>
                <KindBadge kind={ab.kind} />
                <span style={{ fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.4, flex: 1 }}>
                  {ab.title.replace(/^Abstract [A-Z0-9]+:\s*/i, "")}
                </span>
              </div>

              {/* Targets */}
              {ab.targets?.length > 0 && (
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
                  {ab.targets.map((t: string) => (
                    <span key={t} style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 4,
                      background: "#dbeafe", color: "#1e40af", fontWeight: 600,
                    }}>{t}</span>
                  ))}
                </div>
              )}

              {/* Data points */}
              {ab.data_points && Object.keys(ab.data_points).length > 0 && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: ab.conclusion ? 6 : 0 }}>
                  {Object.entries(ab.data_points).map(([k, v]) => (
                    <span key={k} style={{ fontSize: 12, color: "#374151" }}>
                      <span style={{ fontWeight: 600 }}>{k}:</span> {String(v)}
                    </span>
                  ))}
                </div>
              )}

              {/* Conclusion */}
              {ab.conclusion && (
                <p style={{ margin: 0, fontSize: 12, color: "#4b5563", lineHeight: 1.5, fontStyle: "italic" }}>
                  {ab.conclusion}
                </p>
              )}

              {/* DOI link */}
              {ab.doi && (
                <a
                  href={`https://doi.org/${ab.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 11, color: "#2563eb", marginTop: 4, display: "inline-block" }}
                >
                  Abstract ↗
                </a>
              )}
            </div>
          ))}
        </div>

        {/* Chat link */}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #f3f4f6", textAlign: "center" }}>
          <Link
            href={`/chat?q=${encodeURIComponent(`分析 ${data.company} 在 AACR 2026 的数据，结合CRM信息给出BD评估`)}`}
            style={{
              display: "inline-block", padding: "8px 20px", borderRadius: 8,
              background: "#1e3a8a", color: "#fff", fontSize: 13, fontWeight: 600,
              textDecoration: "none",
            }}
          >
            💬 在 Chat 中深度分析
          </Link>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function ConferencePage() {
  const [sessions, setSessions] = useState<ConferenceSession[]>([]);
  const [activeSession, setActiveSession] = useState("AACR-2026");
  const [stats, setStats] = useState<any>(null);

  const [q, setQ] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [country, setCountry] = useState("");
  const [ctOnly, setCtOnly] = useState(false);
  const [page, setPage] = useState(1);

  const [listData, setListData] = useState<ConferenceListResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [companyDetail, setCompanyDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Load sessions on mount
  useEffect(() => {
    fetchConferenceSessions()
      .then(r => setSessions(r.sessions))
      .catch(() => {});
  }, []);

  // Load stats when session changes
  useEffect(() => {
    fetchConferenceStats(activeSession)
      .then(setStats)
      .catch(() => setStats(null));
  }, [activeSession]);

  // Load company list
  const loadCompanies = useCallback(() => {
    setLoading(true);
    fetchConferenceCompanies(activeSession, { q, company_type: companyType, country, ct_only: ctOnly, page })
      .then(data => { setListData(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [activeSession, q, companyType, country, ctOnly, page]);

  useEffect(() => { loadCompanies(); }, [loadCompanies]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [activeSession, q, companyType, country, ctOnly]);

  // Load company detail
  const openCompany = async (name: string) => {
    setSelectedCompany(name);
    setLoadingDetail(true);
    try {
      const { fetchConferenceCompany } = await import("@/lib/api");
      const detail = await fetchConferenceCompany(activeSession, name);
      setCompanyDetail(detail);
    } catch {
      setCompanyDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const activeSessionMeta = sessions.find(s => s.id === activeSession);
  const facets = listData?.facets;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f8fafc" }}>
      {/* Top bar */}
      <div style={{
        background: "#fff", borderBottom: "1px solid #e5e7eb",
        padding: "16px 24px", display: "flex", alignItems: "center", gap: 16, flexShrink: 0,
      }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#111827" }}>会议洞察</h1>
          {activeSessionMeta && (
            <p style={{ margin: "2px 0 0", fontSize: 13, color: "#6b7280" }}>
              {activeSessionMeta.full_name}
              {activeSessionMeta.location && ` · ${activeSessionMeta.location}`}
            </p>
          )}
        </div>

        {/* Session selector */}
        {sessions.length > 1 && (
          <select
            value={activeSession}
            onChange={e => setActiveSession(e.target.value)}
            style={{
              fontSize: 13, padding: "6px 10px", border: "1px solid #d1d5db",
              borderRadius: 7, background: "#fff", color: "#374151", cursor: "pointer",
            }}
          >
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        )}

        {/* Chat shortcut */}
        <Link
          href={`/chat?q=${encodeURIComponent(`分析 ${activeSession} 会议数据，哪些中国公司有CT或LB摘要？`)}`}
          style={{
            display: "flex", alignItems: "center", gap: 6, padding: "7px 14px",
            background: "#1e3a8a", color: "#fff", borderRadius: 8, fontSize: 13,
            fontWeight: 600, textDecoration: "none",
          }}
        >
          💬 Chat 分析
        </Link>
      </div>

      {/* Stats bar */}
      {stats && (
        <div style={{
          background: "#fff", borderBottom: "1px solid #f3f4f6",
          padding: "12px 24px", display: "flex", gap: 24, flexShrink: 0,
          overflowX: "auto",
        }}>
          <StatChip label="BD相关公司" value={stats.total_companies ?? stats.total_bd_heat_companies} color="#1d4ed8" />
          <StatChip label="CT abstracts" value={stats.total_ct} color="#dc2626" />
          <StatChip label="Late-Breaking" value={stats.total_lb} color="#d97706" />
          <StatChip label="摘要总数" value={stats.total_abstracts_covered} color="#6b7280" />
          {stats.by_country?.["中国"] != null && (
            <StatChip label="中国公司" value={stats.by_country["中国"]} color="#166534" />
          )}
        </div>
      )}

      {/* Filters */}
      <div style={{
        background: "#fff", borderBottom: "1px solid #e5e7eb",
        padding: "10px 24px", display: "flex", gap: 8, alignItems: "center",
        flexShrink: 0, flexWrap: "wrap",
      }}>
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="搜索公司名称…"
          style={{
            padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7,
            fontSize: 13, color: "#374151", width: 200,
          }}
        />

        <select
          value={companyType}
          onChange={e => setCompanyType(e.target.value)}
          style={{ fontSize: 13, padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}
        >
          <option value="">所有类型</option>
          {(facets?.types || []).map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        <select
          value={country}
          onChange={e => setCountry(e.target.value)}
          style={{ fontSize: 13, padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}
        >
          <option value="">所有国家</option>
          {(facets?.countries || []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#374151", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={ctOnly}
            onChange={e => setCtOnly(e.target.checked)}
            style={{ width: 14, height: 14, cursor: "pointer" }}
          />
          仅 CT/LB
        </label>

        {(q || companyType || country || ctOnly) && (
          <button
            onClick={() => { setQ(""); setCompanyType(""); setCountry(""); setCtOnly(false); }}
            style={{
              fontSize: 12, padding: "5px 10px", border: "1px solid #d1d5db",
              borderRadius: 6, background: "#f9fafb", cursor: "pointer", color: "#6b7280",
            }}
          >
            重置
          </button>
        )}

        <span style={{ marginLeft: "auto", fontSize: 12, color: "#9ca3af" }}>
          {listData ? `${listData.total} 家公司` : ""}
        </span>
      </div>

      {/* Card grid */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: "#9ca3af", fontSize: 14 }}>
            加载中…
          </div>
        ) : listData?.data.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: "#9ca3af", fontSize: 14 }}>
            没有找到匹配公司
          </div>
        ) : (
          <>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 14,
            }}>
              {listData?.data.map(card => (
                <CompanyCard
                  key={card.company}
                  card={card}
                  sessionId={activeSession}
                  onClick={() => openCompany(card.company)}
                />
              ))}
            </div>

            {/* Pagination */}
            {listData && listData.total_pages > 1 && (
              <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24, alignItems: "center" }}>
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(p => p - 1)}
                  style={{
                    padding: "6px 14px", border: "1px solid #d1d5db", borderRadius: 7,
                    background: page <= 1 ? "#f9fafb" : "#fff", cursor: page <= 1 ? "not-allowed" : "pointer",
                    fontSize: 13, color: page <= 1 ? "#d1d5db" : "#374151",
                  }}
                >← 上一页</button>
                <span style={{ fontSize: 13, color: "#6b7280" }}>
                  {page} / {listData.total_pages}
                </span>
                <button
                  disabled={page >= listData.total_pages}
                  onClick={() => setPage(p => p + 1)}
                  style={{
                    padding: "6px 14px", border: "1px solid #d1d5db", borderRadius: 7,
                    background: page >= listData.total_pages ? "#f9fafb" : "#fff",
                    cursor: page >= listData.total_pages ? "not-allowed" : "pointer",
                    fontSize: 13, color: page >= listData.total_pages ? "#d1d5db" : "#374151",
                  }}
                >下一页 →</button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Company detail modal */}
      {selectedCompany && (
        <CompanyDetailModal
          company={selectedCompany}
          data={loadingDetail ? null : companyDetail}
          onClose={() => { setSelectedCompany(null); setCompanyDetail(null); }}
        />
      )}
    </div>
  );
}

// ─── Stat chip ─────────────────────────────────────────────────────────────────

function StatChip({ label, value, color }: { label: string; value?: number; color: string }) {
  if (value == null) return null;
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 6, flexShrink: 0 }}>
      <span style={{ fontSize: 22, fontWeight: 800, color }}>{value.toLocaleString()}</span>
      <span style={{ fontSize: 12, color: "#6b7280" }}>{label}</span>
    </div>
  );
}
