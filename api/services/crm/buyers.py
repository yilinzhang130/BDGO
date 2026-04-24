"""Buyers domain service — single-entity read for the MNC画像 table.
MNC画像 is public metadata (no per-user visibility), so strip_hidden
is not applied here (mirrors the router, which passes user=None to
list_table_view).
"""

from __future__ import annotations

from crm_store import query_one


def fetch_buyer(name: str) -> dict | None:
    """Return a single MNC画像 row by company_name, or None."""
    return query_one('SELECT * FROM "MNC画像" WHERE "company_name" = ?', (name,))
