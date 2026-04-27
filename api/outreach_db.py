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
        # auth_db's pool sets cursor_factory=RealDictCursor by default, so
        # fetchone() returns a dict. Subscript by column name, not index —
        # the original ``[0]`` raised KeyError(0) in production whenever this
        # ran against PG; it only surfaced after /api/outreach added real-DB
        # integration coverage.
        return int(cur.fetchone()["id"])


# ─────────────────────────────────────────────────────────────
# SELECT
# ─────────────────────────────────────────────────────────────


def _build_event_filters(
    user_id: str,
    *,
    company: str | None,
    status: str | None,
    purpose: str | None,
    perspective: str | None,
    recent_days: int | None,
    search: str | None = None,
) -> tuple[list[str], list[Any]]:
    """Shared WHERE-clause builder for list_events / count_events.

    Kept as a module-private helper so the router and the report service
    agree on what each filter parameter actually means (especially the
    case-insensitive substring matches on `company` and `search`).
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
    if search:
        # Search across the three free-text columns. ILIKE on a small
        # per-user table is fine; revisit if outreach_log grows huge.
        where.append(
            "(to_company ILIKE %s OR COALESCE(to_contact, '') ILIKE %s "
            "OR COALESCE(subject, '') ILIKE %s OR COALESCE(notes, '') ILIKE %s)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    return where, params


def list_events(
    user_id: str,
    *,
    company: str | None = None,
    status: str | None = None,
    purpose: str | None = None,
    perspective: str | None = None,
    recent_days: int | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return events for a user, optionally filtered. Newest first.

    All filters are AND-ed. ``company`` matches case-insensitively (substring).
    ``search`` matches across to_company / to_contact / subject / notes.
    """
    where, params = _build_event_filters(
        user_id,
        company=company,
        status=status,
        purpose=purpose,
        perspective=perspective,
        recent_days=recent_days,
        search=search,
    )

    sql = (
        "SELECT id, to_company, to_contact, purpose, channel, status, "
        "asset_context, perspective, subject, notes, session_id, created_at "
        "FROM outreach_log WHERE " + " AND ".join(where) + " "
        "ORDER BY created_at DESC LIMIT %s OFFSET %s"
    )
    params.extend([int(limit), int(offset)])

    with transaction() as cur:
        cur.cursor_factory = RealDictCursor
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def count_events(
    user_id: str,
    *,
    company: str | None = None,
    status: str | None = None,
    purpose: str | None = None,
    perspective: str | None = None,
    recent_days: int | None = None,
    search: str | None = None,
) -> int:
    """Count events matching the same filters as ``list_events``."""
    where, params = _build_event_filters(
        user_id,
        company=company,
        status=status,
        purpose=purpose,
        perspective=perspective,
        recent_days=recent_days,
        search=search,
    )
    sql = "SELECT COUNT(*) AS n FROM outreach_log WHERE " + " AND ".join(where)
    with transaction() as cur:
        cur.cursor_factory = RealDictCursor
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
    return int(row["n"]) if row else 0


def get_event(user_id: str, event_id: int) -> dict[str, Any] | None:
    """Fetch a single event, scoped to the owning user."""
    with transaction() as cur:
        cur.cursor_factory = RealDictCursor
        cur.execute(
            "SELECT id, to_company, to_contact, purpose, channel, status, "
            "asset_context, perspective, subject, notes, session_id, created_at "
            "FROM outreach_log WHERE id = %s AND user_id = %s",
            (int(event_id), user_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def delete_event(user_id: str, event_id: int) -> bool:
    """Delete one event owned by the user. Returns True if a row was removed."""
    with transaction() as cur:
        cur.execute(
            "DELETE FROM outreach_log WHERE id = %s AND user_id = %s RETURNING id",
            (int(event_id), user_id),
        )
        return cur.fetchone() is not None


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
