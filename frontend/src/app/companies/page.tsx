"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchCompanies, type PaginatedCRM } from "@/lib/api";
import { phaseBadgeClass, priorityBadgeClass } from "@/lib/badges";

const COLUMNS = [
  { key: "客户名称", label: "Company", width: "200px" },
  { key: "客户类型", label: "Type", width: "120px" },
  { key: "所处国家", label: "Country", width: "100px" },
  { key: "核心产品的阶段", label: "Stage", width: "100px" },
  { key: "疾病领域", label: "Disease Area", width: "140px" },
  { key: "公司质量评分", label: "Score", width: "60px" },
  { key: "BD跟进优先级", label: "Priority", width: "70px" },
  { key: "追踪状态", label: "Status", width: "80px" },
];

export default function CompaniesPage() {
  const router = useRouter();
  const [data, setData] = useState<PaginatedCRM | null>(null);
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [type, setType] = useState("");
  const [priority, setPriority] = useState("");
  const [tracked, setTracked] = useState("追踪中");
  const [sort, setSort] = useState("客户名称");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    fetchCompanies({ q, country, type, priority, tracked, sort, order, page, page_size: 50 }).then(
      setData,
    );
  }, [q, country, type, priority, tracked, sort, order, page]);

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
        <h1>Companies ({data?.total ?? "..."})</h1>
      </div>

      <div className="filter-bar">
        <input
          placeholder="Search company..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          style={{ width: 220 }}
        />
        <select
          value={country}
          onChange={(e) => {
            setCountry(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Countries</option>
          {[
            "USA",
            "China",
            "Korea",
            "UK",
            "France",
            "Germany",
            "Japan",
            "Switzerland",
            "Canada",
            "Israel",
          ].map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Types</option>
          {[
            "Biotech(USA)",
            "Biotech(China)",
            "Biotech(Europe)",
            "Biotech(Other)",
            "海外药企",
            "中国药企",
          ].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={priority}
          onChange={(e) => {
            setPriority(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Priorities</option>
          {["A", "B", "C", "D"].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={tracked}
          onChange={(e) => {
            setTracked(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Status</option>
          {["追踪中", "待分类", "排除"].map((s) => (
            <option key={s} value={s}>
              {s}
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
                    style={{ width: col.width }}
                    onClick={() => handleSort(col.key)}
                  >
                    {col.label}
                    {sort === col.key ? (order === "asc" ? " \u25B2" : " \u25BC") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.data?.map((row) => (
                <tr
                  key={String(row["客户名称"] ?? "")}
                  onClick={() =>
                    router.push(`/companies/${encodeURIComponent(String(row["客户名称"] ?? ""))}`)
                  }
                >
                  <td style={{ fontWeight: 600 }}>{row["客户名称"]}</td>
                  <td>{row["客户类型"]}</td>
                  <td>{row["所处国家"]}</td>
                  <td>
                    <span
                      className={`badge ${phaseBadgeClass(String(row["核心产品的阶段"] ?? ""))}`}
                    >
                      {row["核心产品的阶段"] || "-"}
                    </span>
                  </td>
                  <td>{row["疾病领域"] || "-"}</td>
                  <td>{row["公司质量评分"] || "-"}</td>
                  <td>
                    {row["BD跟进优先级"] ? (
                      <span className={`badge ${priorityBadgeClass(String(row["BD跟进优先级"]))}`}>
                        {row["BD跟进优先级"]}
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>{row["追踪状态"] || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && (
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
