"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchDeals, fetchDealsByType } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const COLUMNS = [
  { key: "交易名称", label: "Deal" },
  { key: "交易类型", label: "Type" },
  { key: "买方公司", label: "Buyer" },
  { key: "卖方/合作方", label: "Seller / Partner" },
  { key: "资产名称", label: "Asset" },
  { key: "靶点", label: "Target" },
  { key: "临床阶段", label: "Phase" },
  { key: "首付款($M)", label: "Upfront ($M)" },
  { key: "交易总额($M)", label: "Total ($M)" },
  { key: "宣布日期", label: "Date" },
  { key: "战略评分", label: "Score" },
];

export default function DealsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<any>(null);
  const [dealTypes, setDealTypes] = useState<any[]>([]);
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [type, setType] = useState("");
  const [sort, setSort] = useState("宣布日期");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    fetchDeals({ q, type, page, page_size: 50, sort, order }).then(setData);
  }, [q, type, page, sort, order]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { fetchDealsByType().then(setDealTypes); }, []);

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
        <h1>Deals ({data?.total ?? "..."})</h1>
      </div>

      {dealTypes.length > 0 && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ margin: "0 0 1rem", fontSize: "0.95rem" }}>Deals by Type</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={dealTypes} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="type" type="category" width={120} fontSize={12} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="filter-bar">
        <input
          placeholder="Search deal / company / asset..."
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          style={{ width: 260 }}
        />
        <select value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">All Types</option>
          {dealTypes.map((d) => (
            <option key={d.type} value={d.type}>{d.type} ({d.count})</option>
          ))}
        </select>
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
              {data?.data?.map((d: any) => (
                <tr key={d["交易名称"]} onClick={() => router.push(`/deals/${encodeURIComponent(d["交易名称"])}`)}>
                  <td style={{ fontWeight: 600 }}>{d["交易名称"]}</td>
                  <td>{d["交易类型"] || "-"}</td>
                  <td
                    style={{ cursor: "pointer", color: "var(--accent)" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (d["买方公司"]) router.push(`/companies/${encodeURIComponent(d["买方公司"])}`);
                    }}
                  >
                    {d["买方公司"] || "-"}
                  </td>
                  <td
                    style={{ cursor: "pointer", color: "var(--accent)" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (d["卖方/合作方"]) router.push(`/companies/${encodeURIComponent(d["卖方/合作方"])}`);
                    }}
                  >
                    {d["卖方/合作方"] || "-"}
                  </td>
                  <td>{d["资产名称"] || "-"}</td>
                  <td>{d["靶点"] || "-"}</td>
                  <td>{d["临床阶段"] || "-"}</td>
                  <td>{d["首付款($M)"] || "-"}</td>
                  <td style={{ fontWeight: 600 }}>{d["交易总额($M)"] || "-"}</td>
                  <td>{d["宣布日期"] || "-"}</td>
                  <td>{d["战略评分"] || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && (
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
            <span>Page {data.page} of {data.total_pages}</span>
            <button disabled={page >= data.total_pages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
