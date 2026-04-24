"""Clinical domain service — single-record read for 临床.
List pagination stays in the router (filter DSL = HTTP contract).
"""

from __future__ import annotations

from crm_store import query_one
from field_policy import strip_hidden


def fetch_clinical_record(record_id: str, user: dict) -> dict | None:
    """Return a single 临床 row by 记录ID, or None."""
    row = query_one('SELECT * FROM "临床" WHERE "记录ID" = ?', (record_id,))
    if row is None:
        return None
    return strip_hidden(row, "临床", user)
