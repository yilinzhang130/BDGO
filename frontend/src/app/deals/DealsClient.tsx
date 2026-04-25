"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fetchDeals, type PaginatedCRM, type DealTypeCount } from "@/lib/api";
import { usePaginatedTable } from "@/hooks/usePaginatedTable";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

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

interface Props {
  initialData: PaginatedCRM;
  initialDealTypes: DealTypeCount[];
}

export function DealsClient({ initialData, initialDealTypes }: Props) {
  const router = useRouter();
  const [dealTypes] = useState<DealTypeCount[]>(initialDealTypes);

  const { data, sort, order, handleSort, handleFilter, handlePage } = usePaginatedTable({
    fetchFn: fetchDeals,
    initialData,
    defaultSort: "宣布日期",
    defaultOrder: "desc",
    defaultFilters: { q: "", type: "" },
  });

  return (
    <div>
      <div className="page-header">
        <h1>Deals ({data.total})</h1>
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
          defaultValue=""
          onChange={(e) => handleFilter("q", e.target.value)}
          style={{ width: 260 }}
        />
        <select defaultValue="" onChange={(e) => handleFilter("type", e.target.value)}>
          <option value="">All Types</option>
          {dealTypes.map((d) => (
            <option key={d.type} value={d.type}>
              {d.type} ({d.count})
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    style={{ cursor: "pointer" }}
                  >
                    {col.label}
                    {sort === col.key ? (order === "asc" ? " ▲" : " ▼") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.data?.map((d) => (
                <tr
                  key={String(d["交易名称"] ?? "")}
                  onClick={() =>
                    router.push(`/deals/${encodeURIComponent(String(d["交易名称"] ?? ""))}`)
                  }
                >
                  <td style={{ fontWeight: 600 }}>{d["交易名称"]}</td>
                  <td>{d["交易类型"] || "-"}</td>
                  <td
                    style={{ cursor: "pointer", color: "var(--accent)" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (d["买方公司"])
                        router.push(`/companies/${encodeURIComponent(String(d["买方公司"]))}`);
                    }}
                  >
                    {d["买方公司"] || "-"}
                  </td>
                  <td
                    style={{ cursor: "pointer", color: "var(--accent)" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (d["卖方/合作方"])
                        router.push(`/companies/${encodeURIComponent(String(d["卖方/合作方"]))}`);
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

        {data.total_pages > 1 && (
          <div className="pagination">
            {data.page > 1 ? (
              <button onClick={() => handlePage(data.page - 1)}>Prev</button>
            ) : (
              <span className="disabled">Prev</span>
            )}
            <span>
              Page {data.page} of {data.total_pages}
            </span>
            {data.page < data.total_pages ? (
              <button onClick={() => handlePage(data.page + 1)}>Next</button>
            ) : (
              <span className="disabled">Next</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
