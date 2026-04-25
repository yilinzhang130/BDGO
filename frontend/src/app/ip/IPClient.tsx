"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fetchIP, deleteRecord, type PaginatedCRM } from "@/lib/api";
import { usePaginatedTable } from "@/hooks/usePaginatedTable";
import { statusBadgeClass } from "@/lib/badges";
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

interface Props {
  initialData: PaginatedCRM;
}

export function IPClient({ initialData }: Props) {
  const router = useRouter();
  const [deleting, setDeleting] = useState<string | null>(null);

  const { data, sort, order, handleSort, handleFilter, handlePage } = usePaginatedTable({
    fetchFn: fetchIP,
    initialData,
    defaultSort: "到期日",
    defaultOrder: "asc",
    defaultFilters: { q: "", status: "", jurisdiction: "" },
  });

  const handleDelete = async (patentNo: string) => {
    await deleteRecord("IP", patentNo);
    setDeleting(null);
    // Re-fetch current page by triggering a no-op filter update
    handleFilter("q", "");
  };

  return (
    <div>
      <div className="page-header">
        <h1>IP / Patents ({data.total})</h1>
      </div>

      <div className="filter-bar">
        <input
          placeholder="Search patent / company / asset..."
          defaultValue=""
          onChange={(e) => handleFilter("q", e.target.value)}
          style={{ width: 260 }}
        />
        <select defaultValue="" onChange={(e) => handleFilter("status", e.target.value)}>
          <option value="">All Status</option>
          <option value="有效">Active (有效)</option>
          <option value="已过期">Expired (已过期)</option>
        </select>
        <select defaultValue="" onChange={(e) => handleFilter("jurisdiction", e.target.value)}>
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
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    style={{ cursor: "pointer" }}
                  >
                    {col.label}
                    {sort === col.key ? (order === "asc" ? " ▲" : " ▼") : ""}
                  </th>
                ))}
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {data.data?.map((row) => (
                <tr
                  key={String(row["专利号"] ?? "")}
                  onClick={() =>
                    router.push(`/ip/${encodeURIComponent(String(row["专利号"] ?? ""))}`)
                  }
                >
                  <td style={{ fontWeight: 600 }}>{row["专利号"]}</td>
                  <td>{row["专利持有人"] || "-"}</td>
                  <td>{row["关联资产"] || "-"}</td>
                  <td
                    style={{ cursor: "pointer", color: "var(--accent)" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (row["关联公司"])
                        router.push(`/companies/${encodeURIComponent(String(row["关联公司"]))}`);
                    }}
                  >
                    {row["关联公司"] || "-"}
                  </td>
                  <td>{row["专利类型"] || "-"}</td>
                  <td>{row["到期日"] || "-"}</td>
                  <td>
                    <span className={`badge ${statusBadgeClass(String(row["状态"] ?? ""))}`}>
                      {row["状态"] || "-"}
                    </span>
                  </td>
                  <td>{row["管辖区"] || "-"}</td>
                  <td>{row["Orange_Book"] || "-"}</td>
                  <td>
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleting(String(row["专利号"] ?? ""));
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
