"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { globalSearch, searchSessions } from "@/lib/api";

interface SearchResult {
  type: "company" | "asset" | "deal" | "clinical" | "session";
  title: string;
  subtitle?: string;
  href: string;
}

function groupResults(raw: any, sessions: any[]): SearchResult[] {
  const results: SearchResult[] = [];

  // Sessions first
  for (const s of sessions.slice(0, 3)) {
    results.push({
      type: "session",
      title: s.title || "Untitled Chat",
      subtitle: "对话记录",
      href: `/chat?session=${s.id}`,
    });
  }
  // Companies
  for (const c of (raw?.companies || []).slice(0, 3)) {
    const name = c["客户名称"];
    if (!name) continue;
    results.push({ type: "company", title: name, subtitle: c["客户类型"] || c["所处国家"] || "公司", href: `/companies/${encodeURIComponent(name)}` });
  }
  // Assets
  for (const a of (raw?.assets || []).slice(0, 3)) {
    const name = a["资产名称"];
    if (!name) continue;
    results.push({ type: "asset", title: name, subtitle: `${a["所属客户"] || ""} · ${a["临床阶段"] || ""}`.trim().replace(/^·\s*/, ""), href: `/assets/${encodeURIComponent(a["所属客户"])}/${encodeURIComponent(name)}` });
  }
  // Deals
  for (const d of (raw?.deals || []).slice(0, 2)) {
    const name = d["交易名称"];
    if (!name) continue;
    results.push({ type: "deal", title: name, subtitle: d["交易类型"] || "交易", href: `/deals?q=${encodeURIComponent(name)}` });
  }
  return results;
}

const TYPE_ICON: Record<string, string> = {
  company: "🏢",
  asset: "💊",
  deal: "🤝",
  clinical: "🔬",
  session: "💬",
};

const TYPE_LABEL: Record<string, string> = {
  company: "公司",
  asset: "资产",
  deal: "交易",
  clinical: "临床",
  session: "对话",
};

interface Props {
  open: boolean;
  onClose: () => void;
}

export function SearchModal({ open, onClose }: Props) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const genRef = useRef(0); // incremented each search; stale responses are dropped

  useEffect(() => {
    if (open) {
      setQ("");
      setResults([]);
      setCursor(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const search = useCallback(async (query: string) => {
    const gen = ++genRef.current;
    if (!query.trim()) { setResults([]); return; }
    setLoading(true);
    try {
      const [raw, sessions] = await Promise.all([
        globalSearch(query, 5).catch(() => ({})),
        searchSessions(query, 6).catch(() => []),
      ]);
      if (gen !== genRef.current) return; // stale — a newer query is already in flight
      setResults(groupResults(raw, sessions));
      setCursor(0);
    } catch {
      if (gen === genRef.current) setResults([]);
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(q), 250);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [q, search]);

  const navigate = useCallback((href: string) => {
    router.push(href);
    onClose();
  }, [router, onClose]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setCursor(c => Math.min(c + 1, results.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)); }
      if (e.key === "Enter" && results[cursor]) { navigate(results[cursor].href); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, results, cursor, navigate, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
          zIndex: 1000, backdropFilter: "blur(2px)",
        }}
      />
      {/* Modal */}
      <div style={{
        position: "fixed", top: "12%", left: "50%", transform: "translateX(-50%)",
        width: "min(580px, 90vw)", zIndex: 1001,
        background: "#fff", borderRadius: 16,
        boxShadow: "0 24px 64px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.06)",
        overflow: "hidden",
      }}>
        {/* Input row */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderBottom: "1px solid #f1f5f9" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#94a3b8" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="6.5" cy="6.5" r="4.5" />
            <path d="M10.5 10.5l3 3" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="搜索公司、资产、交易、对话记录…"
            style={{
              flex: 1, border: "none", outline: "none", fontSize: 15,
              background: "transparent", color: "#0f172a",
            }}
          />
          {loading && (
            <span style={{ fontSize: 11, color: "#94a3b8" }}>搜索中…</span>
          )}
          <kbd style={{
            fontSize: 11, color: "#94a3b8", border: "1px solid #e2e8f0",
            borderRadius: 4, padding: "1px 5px", fontFamily: "inherit",
          }}>
            Esc
          </kbd>
        </div>

        {/* Results */}
        {results.length > 0 ? (
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            {results.map((r, i) => (
              <div
                key={`${r.type}-${r.title}`}
                onClick={() => navigate(r.href)}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 16px", cursor: "pointer",
                  background: i === cursor ? "#f1f5ff" : "transparent",
                  transition: "background 0.1s",
                }}
                onMouseEnter={() => setCursor(i)}
              >
                <span style={{ fontSize: 16, width: 24, textAlign: "center" }}>{TYPE_ICON[r.type]}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: "#0f172a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</div>
                  {r.subtitle && <div style={{ fontSize: 12, color: "#64748b", marginTop: 1 }}>{r.subtitle}</div>}
                </div>
                <span style={{
                  fontSize: 10, color: "#94a3b8", background: "#f8faff",
                  border: "1px solid #e2e8f0", borderRadius: 4, padding: "2px 6px",
                  whiteSpace: "nowrap",
                }}>
                  {TYPE_LABEL[r.type]}
                </span>
              </div>
            ))}
          </div>
        ) : q && !loading ? (
          <div style={{ padding: "28px 16px", textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
            未找到 "{q}" 相关结果
          </div>
        ) : !q ? (
          <div style={{ padding: "16px", display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[["💊", "资产", "/assets"], ["🏢", "公司", "/companies"], ["🤝", "交易", "/deals"], ["⚡", "催化剂", "/catalysts"]].map(([icon, label, href]) => (
              <button
                key={label}
                onClick={() => navigate(href)}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
                  background: "#f8faff", border: "1px solid #e2e8f0", borderRadius: 8,
                  cursor: "pointer", fontSize: 13, color: "#374151", fontFamily: "inherit",
                }}
              >
                <span>{icon}</span>{label}
              </button>
            ))}
          </div>
        ) : null}

        {/* Footer hint */}
        <div style={{ padding: "8px 16px", borderTop: "1px solid #f1f5f9", display: "flex", gap: 12, fontSize: 11, color: "#94a3b8" }}>
          <span>↑↓ 导航</span>
          <span>↵ 打开</span>
          <span>Esc 关闭</span>
        </div>
      </div>
    </>
  );
}
