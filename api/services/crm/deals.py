"""Deals domain service — single-entity read for 交易.
List pagination stays in the router (filter DSL = HTTP contract).
"""

from __future__ import annotations

from crm_store import query_one
from field_policy import strip_hidden


def fetch_deal(name: str, user: dict) -> dict | None:
    """Return a single 交易 row by 交易名称, or None."""
    row = query_one('SELECT * FROM "交易" WHERE "交易名称" = ?', (name,))
    if row is None:
        return None
    return strip_hidden(row, "交易", user)
