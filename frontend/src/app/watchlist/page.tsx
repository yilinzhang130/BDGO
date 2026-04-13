"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchWatchlist, removeFromWatchlist } from "@/lib/api";

const TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "company", label: "Company" },
  { value: "asset", label: "Asset" },
  { value: "disease", label: "Disease" },
  { value: "target", label: "Target" },
];

const TYPE_BADGE: Record<string, string> = {
  company: "badge-blue",
  asset: "badge-green",
  disease: "badge-amber",
  target: "badge-purple",
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

      <div className="card" style={{ marginTop: "1rem" }}>
        {data && data.data.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>&#9734;</div>
            <div style={{ fontSize: 15, fontWeight: 500 }}>Your watchlist is empty</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              Star companies, assets, diseases or targets to track them here.
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
