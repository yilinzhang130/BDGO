"""IP domain service — single-entity read for the IP table.
IP rows have no per-user visibility policy, so strip_hidden is not
applied here (mirrors the router, which passes user=None to
list_table_view).
"""

from __future__ import annotations

from crm_store import query_one


def fetch_patent(patent_number: str) -> dict | None:
    """Return a single IP row by 专利号, or None."""
    return query_one('SELECT * FROM "IP" WHERE "专利号" = ?', (patent_number,))
