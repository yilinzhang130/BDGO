"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchWatchlist, removeFromWatchlist, addToWatchlist } from "@/lib/api";

const TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "company", label: "Company" },
  { value: "asset", label: "Asset" },
  { value: "disease", label: "Disease" },
  { value: "target", label: "Target" },
  { value: "incubator", label: "孵化器" },
];

const TYPE_BADGE: Record<string, string> = {
  company: "badge-blue",
  asset: "badge-green",
  disease: "badge-amber",
  target: "badge-purple",
  incubator: "badge-indigo",
};

interface WatchlistItem {
  id: number;
  entity_type: string;
  entity_key: string;
  notes: string | null;
  added_at: string | null;
}

interface WatchlistResponse {
  data: WatchlistItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

function entityHref(type: string, key: string): string | null {
  switch (type) {
    case "company":
      return `/companies/${encodeURIComponent(key)}`;
    case "asset":
      return `/assets/${encodeURIComponent(key)}`;
    default:
      return null;
  }
}

export default function WatchlistPage() {
  const router = useRouter();
  const [data, setData] = useState<WatchlistResponse | null>(null);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  // Quick-add state
  const [addType, setAddType] = useState("company");
  const [addKey, setAddKey] = useState("");
  const [addNotes, setAddNotes] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    try {
      const res = await fetchWatchlist({ q: debouncedQ, type, page, page_size: pageSize });
      setData(res);
    } catch {
      setData(null);
    }
  }, [debouncedQ, type, page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRemove = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await removeFromWatchlist(id);
      load();
    } catch {
      // silent
    }
  };

  const handleRowClick = (item: WatchlistItem) => {
    const href = entityHref(item.entity_type, item.entity_key);
    if (href) router.push(href);
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addKey.trim() || adding) return;
    setAdding(true);
    try {
      await addToWatchlist({ entity_type: addType, entity_key: addKey.trim(), notes: addNotes.trim() || undefined });
      setAddKey("");
      setAddNotes("");
      load();
    } catch (err) {
      console.error("Add to watchlist failed:", err);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div style={{ padding: "2rem" }}>
      <div className="page-header">
        <h1>Watchlist ({data?.total ?? "..."})</h1>
      </div>

      <div className="filter-bar">
        <input
          type="text"
          placeholder="Search..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Quick-add form */}
      <form onSubmit={handleAdd} className="card" style={{ marginTop: "1rem", padding: "0.85rem 1rem", display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)", fontWeight: 500, whiteSpace: "nowrap" }}>+ 添加关注</span>
        <select
          value={addType}
          onChange={(e) => setAddType(e.target.value)}
          style={{ fontSize: "0.82rem", padding: "0.3rem 0.5rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg)", color: "var(--text)" }}
        >
          <option value="company">公司</option>
          <option value="asset">资产</option>
          <option value="disease">疾病</option>
          <option value="target">靶点</option>
          <option value="incubator">孵化器</option>
        </select>
        <input
          type="text"
          placeholder="名称（必填）"
          value={addKey}
          onChange={(e) => setAddKey(e.target.value)}
          required
          style={{ flex: "1 1 160px", fontSize: "0.82rem", padding: "0.3rem 0.6rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg)", color: "var(--text)", minWidth: 120 }}
        />
        <input
          type="text"
          placeholder="备注（可选）"
          value={addNotes}
          onChange={(e) => setAddNotes(e.target.value)}
          style={{ flex: "2 1 200px", fontSize: "0.82rem", padding: "0.3rem 0.6rem", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg)", color: "var(--text)", minWidth: 120 }}
        />
        <button
          type="submit"
          disabled={adding || !addKey.trim()}
          style={{ padding: "0.35rem 0.9rem", background: "var(--accent)", color: "white", border: "none", borderRadius: 6, cursor: adding ? "wait" : "pointer", fontSize: "0.82rem", fontWeight: 600, opacity: adding || !addKey.trim() ? 0.6 : 1, whiteSpace: "nowrap" }}
        >
          {adding ? "添加中…" : "添加"}
        </button>
      </form>

      <div className="card" style={{ marginTop: "1rem" }}>
        {data && data.data.length === 0 ? (
          <div style={{ padding: "3rem 2rem", textAlign: "center", color: "var(--text-secondary)" }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>☆</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)", marginBottom: 8 }}>关注列表为空</div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7, maxWidth: 320, margin: "0 auto" }}>
              进入<strong style={{ color: "var(--accent)" }}>公司</strong>或<strong style={{ color: "var(--accent)" }}>资产</strong>详情页，
              点击标题旁的 ☆ <strong>关注</strong> 按钮，即可将其加入关注列表。
            </div>
          </div>
        ) : (
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Notes</th>
                  <th>Added</th>
                  <th style={{ width: 60 }}></th>
                </tr>
              </thead>
              <tbody>
                {data?.data.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => handleRowClick(item)}
                    style={{ cursor: entityHref(item.entity_type, item.entity_key) ? "pointer" : "default" }}
                  >
                    <td style={{ fontWeight: 500 }}>{item.entity_key}</td>
                    <td>
                      <span className={`badge ${TYPE_BADGE[item.entity_type] || "badge-gray"}`}>
                        {item.entity_type}
                      </span>
                    </td>
                    <td style={{ color: "var(--text-secondary)", maxWidth: 300 }}>{item.notes || "—"}</td>
                    <td style={{ color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                      {item.added_at ? new Date(item.added_at).toLocaleDateString() : "—"}
                    </td>
                    <td>
                      <button
                        className="icon-btn"
                        title="Remove from watchlist"
                        onClick={(e) => handleRemove(item.id, e)}
                        style={{ color: "var(--text-secondary)", fontSize: 14 }}
                      >
                        &#10005;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total_pages > 1 && (
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
            <span>Page {page} of {data.total_pages}</span>
            <button disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
