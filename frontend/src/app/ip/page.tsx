"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchIP, deleteRecord } from "@/lib/api";
import { statusBadgeClass } from "@/lib/utils";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

const COLUMNS = [
  { key: "专利号", label: "Patent #" },
  { key: "专利持有人", label: "Holder" },
  { key: "关联资产", label: "Asset" },
  { key: "关联公司", label: "Company" },
  { key: "专利类型", label: "Type" },
  { key: "到期日", label: "Expiry" },
  { key: "状态", label: "Status" },
  { key: "管辖区", label: "Jurisdiction" },
  { key: "Orange_Book", label: "OB" },
];

export default function IPPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [sort, setSort] = useState("到期日");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchIP({ q, status, jurisdiction, sort, order, page, page_size: 50 }).then(setData);
  }, [q, status, jurisdiction, sort, order, page]);

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

  const handleDelete = async (patentNo: string) => {
    await deleteRecord("IP", patentNo);
    setDeleting(null);
    load();
  };

  return (
    <div>
      <div className="page-header">
        <h1>IP / Patents ({data?.total ?? "..."})</h1>
      </div>

      <div className="filter-bar">
        <input
          placeholder="Search patent / company / asset..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          style={{ width: 260 }}
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Status</option>
          <option value="有效">Active (有效)</option>
          <option value="已过期">Expired (已过期)</option>
        </select>
        <select
          value={jurisdiction}
          onChange={(e) => {
            setJurisdiction(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Jurisdictions</option>
          {["US", "Europe", "China", "Japan", "Korea", "Global"].map((j) => (
            <option key={j} value={j}>
              {j}
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
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {data?.data?.map((row: any) => (
                <tr
                  key={row["专利号"]}
                  onClick={() => router.push(`/ip/${encodeURIComponent(row["专利号"])}`)}
                >
                  <td style={{ fontWeight: 600 }}>{row["专利号"]}</td>
                  <td>{row["专利持有人"] || "-"}</td>
                  <td>{row["关联资产"] || "-"}</td>
                  <td
                    style={{ cursor: "pointer", color: "var(--accent)" }}
                    onClick={() => {
                      if (row["关联公司"])
                        router.push(`/companies/${encodeURIComponent(row["关联公司"])}`);
                    }}
                  >
                    {row["关联公司"] || "-"}
                  </td>
                  <td>{row["专利类型"] || "-"}</td>
                  <td>{row["到期日"] || "-"}</td>
                  <td>
                    <span className={`badge ${statusBadgeClass(row["状态"])}`}>
                      {row["状态"] || "-"}
                    </span>
                  </td>
                  <td>{row["管辖区"] || "-"}</td>
                  <td>{row["Orange_Book"] || "-"}</td>
                  <td>
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleting(row["专利号"]);
                      }}
                      style={{ cursor: "pointer", color: "var(--red)", fontSize: "0.8rem" }}
                      title="Delete"
                    >
                      &#10005;
                    </span>
                  </td>
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

      {deleting && (
        <ConfirmDialog
          message={`Delete patent ${deleting}?`}
          onConfirm={() => handleDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
