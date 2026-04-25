import Link from "next/link";
import { fetchCompaniesServer } from "@/lib/api-server";
import { phaseBadgeClass, priorityBadgeClass } from "@/lib/badges";
import { CompaniesFilters } from "./CompaniesFilters";

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

function sortHref(params: Record<string, string>, col: string): string {
  const sp = new URLSearchParams(params);
  sp.set("sort", col);
  sp.set("order", params.sort === col && params.order === "asc" ? "desc" : "asc");
  sp.delete("page");
  return `?${sp.toString()}`;
}

function pageHref(params: Record<string, string>, pg: number): string {
  const sp = new URLSearchParams(params);
  sp.set("page", String(pg));
  return `?${sp.toString()}`;
}

export default async function CompaniesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const {
    q = "",
    country = "",
    type = "",
    priority = "",
    tracked = "追踪中",
    sort = "客户名称",
    order = "asc",
    page = "1",
  } = params;

  const data = await fetchCompaniesServer({
    q, country, type, priority, tracked, sort, order, page, page_size: "50",
  });

  const pg = data.page;

  return (
    <div>
      <div className="page-header">
        <h1>Companies ({data.total})</h1>
      </div>

      <CompaniesFilters params={params} />

      <div className="card">
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key} style={{ width: col.width }}>
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
                const name = String(row["客户名称"] ?? "");
                return (
                  <tr key={name}>
                    <td style={{ fontWeight: 600 }}>
                      <Link href={`/companies/${encodeURIComponent(name)}`}>{name}</Link>
                    </td>
                    <td>{row["客户类型"]}</td>
                    <td>{row["所处国家"]}</td>
                    <td>
                      <span className={`badge ${phaseBadgeClass(String(row["核心产品的阶段"] ?? ""))}`}>
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
                      ) : "-"}
                    </td>
                    <td>{row["追踪状态"] || "-"}</td>
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
