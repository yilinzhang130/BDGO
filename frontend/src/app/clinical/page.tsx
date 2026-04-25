import Link from "next/link";
import { fetchClinicalServer } from "@/lib/api-server";
import { phaseBadgeClass, resultBadgeClass } from "@/lib/badges";
import { ClinicalFilters } from "./ClinicalFilters";

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

function sortHref(params: Record<string, string>, col: string) {
  const sp = new URLSearchParams(params);
  sp.set("sort", col);
  sp.set("order", params.sort === col && params.order === "asc" ? "desc" : "asc");
  sp.delete("page");
  return `?${sp.toString()}`;
}

function pageHref(params: Record<string, string>, pg: number) {
  const sp = new URLSearchParams(params);
  sp.set("page", String(pg));
  return `?${sp.toString()}`;
}

export default async function ClinicalPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const {
    q = "",
    phase = "",
    status = "",
    result = "",
    sort = "试验ID",
    order = "asc",
    page = "1",
  } = params;

  const data = await fetchClinicalServer({
    q, phase, status, result, sort, order, page, page_size: "50",
  });

  const pg = data.page;

  return (
    <div>
      <div className="page-header">
        <h1>Clinical Trials ({data.total})</h1>
      </div>

      <ClinicalFilters params={params} />

      <div className="card">
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key}>
                    <Link href={sortHref(params, col.key)} scroll={false}>
                      {col.label}
                      {sort === col.key ? (order === "asc" ? " ▲" : " ▼") : ""}
                    </Link>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.data?.map((row) => {
                const id = String(row["试验ID"] ?? "");
                return (
                  <tr key={id}>
                    <td>
                      <Link href={`/clinical/${encodeURIComponent(id)}`}>{id}</Link>
                    </td>
                    <td>
                      <Link href={`/companies/${encodeURIComponent(String(row["公司名称"] ?? ""))}`}>
                        {row["公司名称"]}
                      </Link>
                    </td>
                    <td>{row["资产名称"] || "-"}</td>
                    <td>{row["适应症"] || "-"}</td>
                    <td>
                      <span className={`badge ${phaseBadgeClass(String(row["临床期次"] ?? ""))}`}>
                        {row["临床期次"] || "-"}
                      </span>
                    </td>
                    <td>{row["主要终点名称"] || "-"}</td>
                    <td>{row["主要终点结果值"] || "-"}</td>
                    <td>
                      {row["结果判定"] ? (
                        <span className={`badge ${resultBadgeClass(String(row["结果判定"]))}`}>
                          {row["结果判定"]}
                        </span>
                      ) : "-"}
                    </td>
                    <td>{row["安全性标志"] || "-"}</td>
                    <td>{row["数据状态"] || "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {data.total_pages > 1 && (
          <div className="pagination">
            {pg > 1 ? (
              <Link href={pageHref(params, pg - 1)} scroll={false}>Prev</Link>
            ) : (
              <span className="disabled">Prev</span>
            )}
            <span>Page {pg} of {data.total_pages}</span>
            {pg < data.total_pages ? (
              <Link href={pageHref(params, pg + 1)} scroll={false}>Next</Link>
            ) : (
              <span className="disabled">Next</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
