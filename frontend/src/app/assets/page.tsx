import Link from "next/link";
import { fetchAssetsServer } from "@/lib/api-server";
import { phaseBadgeClass } from "@/lib/badges";
import { AssetsFilters } from "./AssetsFilters";

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

export default async function AssetsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const {
    q = "",
    phase = "",
    disease = "",
    scored = "",
    tracked = "追踪中",
    sort = "资产名称",
    order = "asc",
    page = "1",
  } = params;

  const data = await fetchAssetsServer({
    q,
    phase,
    disease,
    scored,
    tracked,
    sort,
    order,
    page,
    page_size: "50",
  });

  const pg = data.page;

  return (
    <div>
      <div className="page-header">
        <h1>Assets ({data.total})</h1>
      </div>

      <AssetsFilters params={params} />

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
                const name = String(row["资产名称"] ?? "");
                const company = String(row["所属客户"] ?? "");
                return (
                  <tr key={name}>
                    <td style={{ fontWeight: 600 }}>
                      <Link
                        href={`/assets/${encodeURIComponent(company)}/${encodeURIComponent(name)}`}
                      >
                        {name}
                      </Link>
                    </td>
                    <td>
                      <Link href={`/companies/${encodeURIComponent(company)}`}>{company}</Link>
                    </td>
                    <td>{row["技术平台类别"] || "-"}</td>
                    <td>{row["疾病领域"] || "-"}</td>
                    <td>
                      <span className={`badge ${phaseBadgeClass(String(row["临床阶段"] ?? ""))}`}>
                        {row["临床阶段"] || "-"}
                      </span>
                    </td>
                    <td>{row["靶点"] || "-"}</td>
                    <td>{row["作用机制(MOA)"] || "-"}</td>
                    <td>{row["质量评分"] || "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {data.total_pages > 1 && (
          <div className="pagination">
            {pg > 1 ? (
              <Link href={pageHref(params, pg - 1)} scroll={false}>
                Prev
              </Link>
            ) : (
              <span className="disabled">Prev</span>
            )}
            <span>
              Page {pg} of {data.total_pages}
            </span>
            {pg < data.total_pages ? (
              <Link href={pageHref(params, pg + 1)} scroll={false}>
                Next
              </Link>
            ) : (
              <span className="disabled">Next</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
