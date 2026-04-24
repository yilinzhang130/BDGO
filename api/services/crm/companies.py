"""Companies domain service — CRM reads for the 公司 table and its
related single-entity views (assets / trials / deals for a company).

Pattern established by S-002 pilot: router owns HTTP contract +
query-param validation; service owns SQL + field visibility policy.
List pagination uses ``list_table_view`` directly in the router
because the per-endpoint filter DSL IS the HTTP contract and doesn't
belong behind a service.
"""

from __future__ import annotations

from crm_store import paginate, query, query_one
from field_policy import strip_hidden


def fetch_company(name: str, user: dict) -> dict | None:
    """Return a single 公司 row with hidden fields stripped, or None."""
    row = query_one('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))
    if row is None:
        return None
    return strip_hidden(row, "公司", user)


def fetch_company_assets(name: str, page: int, page_size: int, user: dict) -> dict:
    """Paginated 资产 rows scoped to a company. Sorted by 临床阶段 ascending."""
    result = paginate(
        "资产",
        where='"所属客户" = ?',
        params=(name,),
        order_by='"临床阶段" ASC',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "资产", user)
    return result


def fetch_company_trials(name: str, page: int, page_size: int, user: dict) -> dict:
    """Paginated 临床 rows for the company. Sorted by 数据状态 ascending."""
    result = paginate(
        "临床",
        where='"公司名称" = ?',
        params=(name,),
        order_by='"数据状态" ASC',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "临床", user)
    return result


def fetch_company_deals(name: str, user: dict) -> list[dict]:
    """All 交易 rows where the company is either the buyer or the seller,
    newest announcement first. Unpaginated because deal counts per
    company are low single digits in practice."""
    rows = query(
        'SELECT * FROM "交易" WHERE "买方公司" = ? OR "卖方/合作方" = ? '
        'ORDER BY "宣布日期" DESC',
        (name, name),
    )
    return strip_hidden(rows, "交易", user)
