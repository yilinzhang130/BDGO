"""
outreach_db.py — Postgres helpers for the outreach_log event stream.

Append-only model. Each row is one outreach event at a point in time —
to record a status change, INSERT a new row with the new status, do NOT
UPDATE the prior row. The chat-facing `/log` and `/outreach` services
call into this module.

Schema lives in auth_db.py (bootstrap DDL) + migrations/versions/
20260426_0001_outreach_log_cd82ef9a1578.py.
"""

from __future__ import annotations

import logging
from typing import Any

from auth_db import transaction
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Validation constants
# ─────────────────────────────────────────────────────────────

PURPOSES = (
    "cold_outreach",
    "cda_followup",
    "data_room_request",
    "term_sheet_send",
    "meeting_request",
    "follow_up",
    "other",
)

CHANNELS = ("email", "linkedin", "phone", "in_person", "other")

STATUSES = (
    "sent",
    "replied",
    "meeting",
    "cda_signed",
    "ts_signed",
    "definitive_signed",
    "passed",
    "dead",
)

PERSPECTIVES = ("buyer", "seller")


# ─────────────────────────────────────────────────────────────
# INSERT
# ─────────────────────────────────────────────────────────────


def insert_event(
    *,
    user_id: str,
    to_company: str,
    purpose: str,
    channel: str = "email",
    status: str = "sent",
    to_contact: str | None = None,
    asset_context: str | None = None,
    perspective: str | None = None,
    subject: str | None = None,
    notes: str | None = None,
    session_id: str | None = None,
) -> int:
    """Insert a single outreach event. Returns new row id."""
    with transaction() as cur:
        cur.execute(
            """
            INSERT INTO outreach_log (
                user_id, session_id, to_company, to_contact, purpose,
                channel, status, asset_context, perspective, subject, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                session_id,
                to_company,
                to_contact,
                purpose,
                channel,
                status,
                asset_context,
                perspective,
                subject,
                notes,
            ),
        )
        return cur.fetchone()[0]


# ─────────────────────────────────────────────────────────────
# SELECT
# ─────────────────────────────────────────────────────────────


def list_events(
    user_id: str,
    *,
    company: str | None = None,
    status: str | None = None,
    purpose: str | None = None,
    perspective: str | None = None,
    recent_days: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return events for a user, optionally filtered. Newest first.

    All filters are AND-ed. ``company`` matches case-insensitively (substring).
    """
    where = ["user_id = %s"]
    params: list[Any] = [user_id]

    if company:
        where.append("to_company ILIKE %s")
        params.append(f"%{company}%")
    if status:
        where.append("status = %s")
        params.append(status)
    if purpose:
        where.append("purpose = %s")
        params.append(purpose)
    if perspective:
        where.append("perspective = %s")
        params.append(perspective)
    if recent_days is not None and recent_days > 0:
        where.append("created_at >= NOW() - (%s::int * INTERVAL '1 day')")
        params.append(recent_days)

    sql = (
        "SELECT id, to_company, to_contact, purpose, channel, status, "
        "asset_context, perspective, subject, notes, session_id, created_at "
        "FROM outreach_log WHERE " + " AND ".join(where) + " "
        "ORDER BY created_at DESC LIMIT %s"
    )
    params.append(int(limit))

    with transaction() as cur:
        cur.cursor_factory = RealDictCursor
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# Aggregations
# ─────────────────────────────────────────────────────────────


def status_counts_per_company(
    user_id: str, *, recent_days: int | None = None
) -> list[dict[str, Any]]:
    """Per-company status counts. Used by the /outreach pipeline view."""
    where = ["user_id = %s"]
    params: list[Any] = [user_id]
    if recent_days is not None and recent_days > 0:
        where.append("created_at >= NOW() - (%s::int * INTERVAL '1 day')")
        params.append(recent_days)

    sql = (
        "SELECT to_company, status, COUNT(*) AS n, "
        "MAX(created_at) AS last_touched "
        "FROM outreach_log WHERE " + " AND ".join(where) + " "
        "GROUP BY to_company, status "
        "ORDER BY MAX(created_at) DESC"
    )
    with transaction() as cur:
        cur.cursor_factory = RealDictCursor
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]
