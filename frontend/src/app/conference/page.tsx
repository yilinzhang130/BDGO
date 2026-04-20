"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchConferenceSessions,
  fetchConferenceStats,
  fetchConferenceCompanies,
  fetchConferenceAbstracts,
  ConferenceSession,
  ConferenceCompanyCard,
  ConferenceAbstract,
} from "@/lib/api";
import {
  AbstractCard,
  CompanyCard,
  StatChip,
} from "@/components/conference/ConferenceCards";
import { AbstractDetailModal } from "@/components/conference/AbstractDetailModal";
import { ConferenceChatSidebar } from "@/components/conference/ConferenceChatSidebar";

type ViewMode = "abstracts" | "companies";

interface ConferenceStats {
  total_companies?: number;
  total_bd_heat_companies?: number;
  total_ct?: number;
  total_lb?: number;
  by_country?: Record<string, number>;
}

interface Facets {
  types?: string[];
  countries?: string[];
}

interface AbstractsPage {
  data?: ConferenceAbstract[];
  facets?: Facets;
  total?: number;
  total_pages?: number;
}

interface CompaniesPage {
  data?: ConferenceCompanyCard[];
  facets?: Facets;
  total?: number;
  total_pages?: number;
}

export default function ConferencePage() {
  const [sessions, setSessions] = useState<ConferenceSession[]>([]);
  const [activeSession, setActiveSession] = useState("AACR-2026");
  const [stats, setStats] = useState<ConferenceStats | null>(null);
  const [view, setView] = useState<ViewMode>("abstracts");

  // Shared filters
  const [q, setQ] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [country, setCountry] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);

  const [abstracts, setAbstracts] = useState<AbstractsPage | null>(null);
  const [loadingAbs, setLoadingAbs] = useState(false);

  const [companies, setCompanies] = useState<CompaniesPage | null>(null);
  const [loadingCo, setLoadingCo] = useState(false);

  const [selectedAb, setSelectedAb] = useState<ConferenceAbstract | null>(null);

  // Pending question fed into the sidebar chat (from detail modal).
  const [pendingAsk, setPendingAsk] = useState<string | null>(null);

  useEffect(() => {
    fetchConferenceSessions()
      .then(r => setSessions(r.sessions))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchConferenceStats(activeSession).then(setStats).catch(() => setStats(null));
  }, [activeSession]);

  const loadAbstracts = useCallback(() => {
    setLoadingAbs(true);
    fetchConferenceAbstracts(activeSession, { q, company_type: companyType, country, kind, page })
      .then(d => { setAbstracts(d); setLoadingAbs(false); })
      .catch(() => setLoadingAbs(false));
  }, [activeSession, q, companyType, country, kind, page]);

  const loadCompanies = useCallback(() => {
    setLoadingCo(true);
    fetchConferenceCompanies(activeSession, {
      q, company_type: companyType, country, ct_only: kind === "CT",
      page, page_size: 24,
    })
      .then(d => { setCompanies(d); setLoadingCo(false); })
      .catch(() => setLoadingCo(false));
  }, [activeSession, q, companyType, country, kind, page]);

  useEffect(() => {
    if (view === "abstracts") loadAbstracts();
    else loadCompanies();
  }, [view, loadAbstracts, loadCompanies]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [activeSession, q, companyType, country, kind, view]);

  const activeSessionMeta = sessions.find(s => s.id === activeSession);
  const facets = view === "abstracts" ? abstracts?.facets : companies?.facets;
  const currentData = view === "abstracts" ? abstracts : companies;
  const isLoading = view === "abstracts" ? loadingAbs : loadingCo;
  const totalItems = currentData?.total ?? 0;
  const totalPages = currentData?.total_pages ?? 1;

  return (
    <div style={{ display: "flex", height: "100vh", background: "#f8fafc", overflow: "hidden" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        <div style={{
          background: "#fff", borderBottom: "1px solid #e5e7eb",
          padding: "14px 24px", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#111827" }}>
                {activeSessionMeta?.full_name || activeSession}
              </h1>
              {activeSessionMeta?.location && (
                <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 1 }}>{activeSessionMeta.location}</div>
              )}
            </div>

            {sessions.length > 1 && (
              <select
                value={activeSession}
                onChange={e => setActiveSession(e.target.value)}
                style={{ fontSize: 13, padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}
              >
                {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
          </div>

          {stats && (
            <div style={{ display: "flex", gap: 20, marginBottom: 12, flexWrap: "wrap" }}>
              <StatChip icon="🏢" label="BD公司" value={stats.total_companies ?? stats.total_bd_heat_companies} color="#1d4ed8" />
              <StatChip icon="🔴" label="CT摘要" value={stats.total_ct} color="#dc2626" />
              <StatChip icon="🟠" label="Late-Breaking" value={stats.total_lb} color="#d97706" />
              <StatChip icon="🇨🇳" label="中国公司" value={stats.by_country?.["中国"]} color="#166534" />
            </div>
          )}

          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{
              display: "flex", border: "1px solid #d1d5db", borderRadius: 8, overflow: "hidden",
              flexShrink: 0,
            }}>
              {([["abstracts", "摘要卡片"], ["companies", "公司视图"]] as const).map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  style={{
                    padding: "6px 14px", fontSize: 12, fontWeight: 600, border: "none",
                    background: view === v ? "#1e3a8a" : "#fff",
                    color: view === v ? "#fff" : "#6b7280",
                    cursor: "pointer", transition: "all 0.1s",
                  }}
                >{label}</button>
              ))}
            </div>

            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder={view === "abstracts" ? "搜索标题/靶点/公司…" : "搜索公司名称…"}
              style={{
                padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7,
                fontSize: 13, color: "#374151", width: 200,
              }}
            />

            <select value={companyType} onChange={e => setCompanyType(e.target.value)}
              style={{ fontSize: 13, padding: "6px 9px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}>
              <option value="">所有类型</option>
              {(facets?.types || []).map((t: string) => <option key={t} value={t}>{t}</option>)}
            </select>

            <select value={country} onChange={e => setCountry(e.target.value)}
              style={{ fontSize: 13, padding: "6px 9px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}>
              <option value="">所有国家</option>
              {(facets?.countries || []).map((c: string) => <option key={c} value={c}>{c}</option>)}
            </select>

            {view === "abstracts" && (
              <select value={kind} onChange={e => setKind(e.target.value)}
                style={{ fontSize: 13, padding: "6px 9px", border: "1px solid #d1d5db", borderRadius: 7, color: "#374151" }}>
                <option value="">全部类型</option>
                <option value="CT">Clinical Trial (CT)</option>
                <option value="LB">Late-Breaking (LB)</option>
                <option value="regular">Poster</option>
              </select>
            )}

            {(q || companyType || country || kind) && (
              <button
                onClick={() => { setQ(""); setCompanyType(""); setCountry(""); setKind(""); }}
                style={{ fontSize: 12, padding: "5px 10px", border: "1px solid #d1d5db", borderRadius: 6, background: "#f9fafb", cursor: "pointer", color: "#6b7280" }}
              >重置</button>
            )}

            <span style={{ marginLeft: "auto", fontSize: 12, color: "#9ca3af" }}>
              {totalItems > 0 ? `${totalItems} 条` : ""}
            </span>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {isLoading ? (
            <div style={{ textAlign: "center", padding: "80px 0", color: "#9ca3af", fontSize: 14 }}>加载中…</div>
          ) : totalItems === 0 ? (
            <div style={{ textAlign: "center", padding: "80px 0", color: "#9ca3af" }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
              <div style={{ fontSize: 14 }}>没有找到匹配数据</div>
            </div>
          ) : (
            <>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: 14,
              }}>
                {view === "abstracts"
                  ? (abstracts?.data || []).map((ab, i) => (
                    <AbstractCard key={i} ab={ab} onClick={() => setSelectedAb(ab)} />
                  ))
                  : (companies?.data || []).map((card, i) => (
                    <CompanyCard key={i} card={card} onClick={() => {
                      setQ(card.company); setView("abstracts");
                    }} />
                  ))
                }
              </div>

              {totalPages > 1 && (
                <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 28, alignItems: "center" }}>
                  <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    style={{
                      padding: "7px 16px", border: "1px solid #d1d5db", borderRadius: 7,
                      background: page <= 1 ? "#f9fafb" : "#fff", cursor: page <= 1 ? "not-allowed" : "pointer",
                      fontSize: 13, color: page <= 1 ? "#d1d5db" : "#374151",
                    }}>← 上一页</button>
                  <span style={{ fontSize: 13, color: "#6b7280" }}>{page} / {totalPages}</span>
                  <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    style={{
                      padding: "7px 16px", border: "1px solid #d1d5db", borderRadius: 7,
                      background: page >= totalPages ? "#f9fafb" : "#fff",
                      cursor: page >= totalPages ? "not-allowed" : "pointer",
                      fontSize: 13, color: page >= totalPages ? "#d1d5db" : "#374151",
                    }}>下一页 →</button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <ConferenceChatSidebar
        session={activeSession}
        contextHint={view === "abstracts" ? `摘要视图${kind ? "-" + kind : ""}${country ? "-" + country : ""}` : "公司视图"}
        pendingAsk={pendingAsk}
        onAskConsumed={() => setPendingAsk(null)}
      />

      <AbstractDetailModal
        ab={selectedAb}
        onClose={() => setSelectedAb(null)}
        onAsk={(q) => setPendingAsk(q)}
      />
    </div>
  );
}
