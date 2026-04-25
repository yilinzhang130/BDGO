import Link from "next/link";
import { fetchBuyersServer } from "@/lib/api-server";
import { BuyersFilters } from "./BuyersFilters";

const COLUMNS = [
  { key: "company_name", label: "Company" },
  { key: "heritage_ta", label: "Heritage TA" },
  { key: "risk_appetite", label: "Risk Appetite" },
  { key: "deal_size_preference", label: "Deal Size" },
  { key: "annual_revenue", label: "Revenue" },
  { key: "ceo_name", label: "CEO" },
  { key: "head_bd_name", label: "Head of BD" },
  { key: "last_updated", label: "Updated" },
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

export default async function BuyersPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const {
    q = "",
    sort = "company_name",
    order = "asc",
    page = "1",
  } = params;

  const data = await fetchBuyersServer({ q, sort, order, page, page_size: "50" });
  const pg = data.page;

  return (
    <div>
      <div className="page-header">
        <h1>MNC Buyer Profiles ({data.total})</h1>
      </div>

      <BuyersFilters params={params} />

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
              {data.data?.map((b) => {
                const name = String(b.company_name ?? "");
                return (
                  <tr key={name}>
                    <td style={{ fontWeight: 600 }}>
                      <Link href={`/buyers/${encodeURIComponent(name)}`}>{name}</Link>
                    </td>
                    <td>{b.heritage_ta || "-"}</td>
                    <td>{b.risk_appetite || "-"}</td>
                    <td>{b.deal_size_preference || "-"}</td>
                    <td>{b.annual_revenue || "-"}</td>
                    <td>{b.ceo_name || "-"}</td>
                    <td>{b.head_bd_name || "-"}</td>
                    <td>{b.last_updated || "-"}</td>
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
