"""Shared list-endpoint helper for CRUD routers.

Every CRM list endpoint follows the same 3-step dance after filter
assembly: validate the sort column against an allowlist, paginate, then
strip hidden fields based on the caller's visibility. This module
centralises that dance so the 6 CRUD routers (assets / buyers /
clinical / companies / deals / ip) don't redeclare it.

Filter building stays in each router — the column-to-query-param
mapping IS the endpoint's contract, and some routers need custom SQL
(e.g. ``scored=yes``). Callers hand the pre-built ``where`` + ``params``
to this helper.
"""

from __future__ import annotations

from crm_store import paginate
from field_policy import strip_hidden


def list_table_view(
    table: str,
    *,
    where: str,
    params: tuple,
    sort: str,
    order: str,
    sort_allowlist: set[str],
    default_sort: str,
    page: int,
    page_size: int,
    user: dict | None = None,
) -> dict:
    """Run the standard ``sort-validate → paginate → strip_hidden`` pipeline.

    The sort allowlist is a per-table business rule (sortable columns are
    a UX contract), so it's passed in rather than derived — don't move it
    into this module.

    Pass ``user=None`` for tables that don't have per-user field visibility
    (e.g. the MNC画像 buyer table and IP table). In that case the
    strip-hidden step is skipped.
    """
    sort_col = sort if sort in sort_allowlist else default_sort
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    result = paginate(
        table,
        where=where,
        params=params,
        order_by=f'"{sort_col}" {order_dir}',
        page=page,
        page_size=page_size,
    )
    if user is not None:
        result["data"] = strip_hidden(result["data"], table, user)
    return result
