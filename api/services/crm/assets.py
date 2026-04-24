"""Assets domain service — single-entity reads for the 资产 table.
List pagination stays in the router because the per-endpoint filter
DSL IS the HTTP contract (see services/crm/companies for rationale).
"""

from __future__ import annotations

from crm_store import paginate, query_one
from field_policy import strip_hidden


def fetch_asset(company: str, name: str, user: dict) -> dict | None:
    """Return a single 资产 row (keyed by 资产名称+所属客户), or None."""
    row = query_one(
        'SELECT * FROM "资产" WHERE "资产名称" = ? AND "所属客户" = ?',
        (name, company),
    )
    if row is None:
        return None
    return strip_hidden(row, "资产", user)


def fetch_asset_trials(company: str, name: str, page: int, page_size: int, user: dict) -> dict:
    """Paginated 临床 rows for an asset, sorted by 临床期次 ascending."""
    result = paginate(
        "临床",
        where='"资产名称" = ? AND "公司名称" = ?',
        params=(name, company),
        order_by='"临床期次" ASC',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "临床", user)
    return result
