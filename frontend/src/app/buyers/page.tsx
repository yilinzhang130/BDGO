"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchBuyers } from "@/lib/api";

const COLUMNS = [
  { key: "company_name", label: "Company" },
  { key: "heritage_ta", label: "Heritage TA" },
  { key: "risk_appetite", label: "Risk Appetite" },
  { key: "deal_size_preference", label: "Deal Size" },
  { key: "annual_revenue", label: "Revenue" },
  { key: "ceo_name", label: "CEO" },
  { key: "head_bd_name", label: "Head of BD" },
  { key: "last_updated", label: "Updated" },
];

export default function BuyersPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("company_name");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    fetchBuyers({ q, sort, order, page, page_size: 50 }).then(setData);
  }, [q, sort, order, page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSort = (col: string) => {
    if (sort === col) {
      setOrder(order === "asc" ? "desc" : "asc");
    } else {
      setSort(col);
      setOrder("asc");
    }
    setPage(1);
  };

  return (
    <div>
      <div className="page-header">
        <h1>MNC Buyer Profiles ({data?.total ?? "..."})</h1>
      </div>

      <div className="filter-bar">
        <input
          placeholder="Search buyer company..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          style={{ width: 260 }}
        />
      </div>

      <div className="card">
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key} onClick={() => handleSort(col.key)}>
                    {col.label}
                    {sort === col.key ? (order === "asc" ? " \u25B2" : " \u25BC") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.data?.map((b: any) => (
                <tr
                  key={b.company_name}
                  onClick={() => router.push(`/buyers/${encodeURIComponent(b.company_name)}`)}
                >
                  <td style={{ fontWeight: 600 }}>{b.company_name}</td>
                  <td>{b.heritage_ta || "-"}</td>
                  <td>{b.risk_appetite || "-"}</td>
                  <td>{b.deal_size_preference || "-"}</td>
                  <td>{b.annual_revenue || "-"}</td>
                  <td>{b.ceo_name || "-"}</td>
                  <td>{b.head_bd_name || "-"}</td>
                  <td>{b.last_updated || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Prev
            </button>
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            <button disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
