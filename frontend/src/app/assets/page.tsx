"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchAssets } from "@/lib/api";
import { phaseBadgeClass } from "@/lib/badges";

const COLUMNS = [
  { key: "资产名称", label: "Asset" },
  { key: "所属客户", label: "Company" },
  { key: "技术平台类别", label: "Platform" },
  { key: "疾病领域", label: "Disease" },
  { key: "临床阶段", label: "Phase" },
  { key: "靶点", label: "Target" },
  { key: "作用机制(MOA)", label: "MOA" },
  { key: "质量评分", label: "Q Score" },
];

export default function AssetsPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [q, setQ] = useState("");
  const [phase, setPhase] = useState("");
  const [disease, setDisease] = useState("");
  const [scored, setScored] = useState("");
  const [tracked, setTracked] = useState("追踪中");
  const [sort, setSort] = useState("资产名称");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    fetchAssets({ q, phase, disease, scored, tracked, sort, order, page, page_size: 50 }).then(
      setData,
    );
  }, [q, phase, disease, scored, tracked, sort, order, page]);

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
        <h1>Assets ({data?.total ?? "..."})</h1>
      </div>

      <div className="filter-bar">
        <input
          placeholder="Search asset / target..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          style={{ width: 220 }}
        />
        <select
          value={phase}
          onChange={(e) => {
            setPhase(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Phases</option>
          {[
            "Pre-clinical",
            "Phase 1",
            "Phase 1/2",
            "Phase 2",
            "Phase 2/3",
            "Phase 3",
            "Phase 4",
            "Approved",
          ].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={disease}
          onChange={(e) => {
            setDisease(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Disease Areas</option>
          {[
            "Oncology",
            "Immunology",
            "Neurology",
            "Rare Disease",
            "Cardiology",
            "Infectious Disease",
            "Metabolic",
            "Ophthalmology",
          ].map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          value={scored}
          onChange={(e) => {
            setScored(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          <option value="yes">With Q Scores</option>
        </select>
        <select
          value={tracked}
          onChange={(e) => {
            setTracked(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Status</option>
          {["追踪中", "待分类", "非追踪"].map((s) => (
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
                  <th key={col.key} onClick={() => handleSort(col.key)}>
                    {col.label}
                    {sort === col.key ? (order === "asc" ? " \u25B2" : " \u25BC") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.data?.map((a: any, i: number) => (
                <tr
                  key={`${a["资产名称"]}-${a["所属客户"]}-${i}`}
                  onClick={() =>
                    router.push(
                      `/assets/${encodeURIComponent(a["所属客户"])}/${encodeURIComponent(a["资产名称"])}`,
                    )
                  }
                >
                  <td style={{ fontWeight: 600 }}>{a["资产名称"]}</td>
                  <td>{a["所属客户"]}</td>
                  <td>{a["技术平台类别"] || "-"}</td>
                  <td>{a["疾病领域"] || "-"}</td>
                  <td>
                    <span className={`badge ${phaseBadgeClass(a["临床阶段"])}`}>
                      {a["临床阶段"] || "-"}
                    </span>
                  </td>
                  <td>{a["靶点"] || "-"}</td>
                  <td>{a["作用机制(MOA)"]?.slice(0, 30) || "-"}</td>
                  <td>{a["质量评分"] || "-"}</td>
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
