"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchClinical } from "@/lib/api";
import { phaseBadgeClass, resultBadgeClass } from "@/lib/badges";

const COLUMNS = [
  { key: "试验ID", label: "Trial ID" },
  { key: "公司名称", label: "Company" },
  { key: "资产名称", label: "Asset" },
  { key: "适应症", label: "Indication" },
  { key: "临床期次", label: "Phase" },
  { key: "主要终点名称", label: "Primary Endpoint" },
  { key: "主要终点结果值", label: "Value" },
  { key: "结果判定", label: "Result" },
  { key: "安全性标志", label: "Safety" },
  { key: "数据状态", label: "Status" },
];

export default function ClinicalPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [q, setQ] = useState("");
  const [phase, setPhase] = useState("");
  const [status, setStatus] = useState("");
  const [result, setResult] = useState("");
  const [sort, setSort] = useState("试验ID");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    fetchClinical({ q, phase, status, result, sort, order, page, page_size: 50 }).then(setData);
  }, [q, phase, status, result, sort, order, page]);

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
        <h1>Clinical Trials ({data?.total ?? "..."})</h1>
      </div>

      <div className="filter-bar">
        <input
          placeholder="Search trial / company / asset..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          style={{ width: 260 }}
        />
        <select
          value={phase}
          onChange={(e) => {
            setPhase(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Phases</option>
          {["Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3", "Phase 4"].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Status</option>
          {["已读出", "进行中", "入组中", "待读出", "终止", "撤回"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={result}
          onChange={(e) => {
            setResult(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Results</option>
          {["积极", "混合", "阴性", "未达成"].map((r) => (
            <option key={r} value={r}>
              {r}
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
                  <th key={col.key} onClick={() => handleSort(col.key)}>
                    {col.label}
                    {sort === col.key ? (order === "asc" ? " \u25B2" : " \u25BC") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.data?.map((t: any) => (
                <tr
                  key={t["记录ID"]}
                  onClick={() => router.push(`/clinical/${encodeURIComponent(t["记录ID"])}`)}
                >
                  <td style={{ fontWeight: 500 }}>{t["试验ID"]}</td>
                  <td>{t["公司名称"] || "-"}</td>
                  <td>{t["资产名称"] || "-"}</td>
                  <td>{t["适应症"]?.slice(0, 30) || "-"}</td>
                  <td>
                    <span className={`badge ${phaseBadgeClass(t["临床期次"])}`}>
                      {t["临床期次"] || "-"}
                    </span>
                  </td>
                  <td>{t["主要终点名称"] || "-"}</td>
                  <td>
                    {t["主要终点结果值"] != null
                      ? `${t["主要终点结果值"]}${t["主要终点单位"] || ""}`
                      : "-"}
                  </td>
                  <td>
                    <span className={`badge ${resultBadgeClass(t["结果判定"])}`}>
                      {t["结果判定"] || "-"}
                    </span>
                  </td>
                  <td>{t["安全性标志"] || "-"}</td>
                  <td>{t["数据状态"] || "-"}</td>
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
