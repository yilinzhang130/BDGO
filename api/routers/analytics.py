"""Analytics endpoints — event tracking + funnel metrics (P1-9).

POST /api/analytics/event         — write one analytics event (all users, fire-and-forget)
GET  /api/analytics/outreach-funnel — outreach conversion funnel (admin only)
GET  /api/analytics/slash-usage     — slash command usage from report_history (admin only)
"""

from __future__ import annotations

import json
import logging

from auth import get_current_user
from auth_db import transaction
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EventBody(BaseModel):
    event: str = Field(..., max_length=100)
    properties: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_admin(user: dict) -> None:
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin only")


def _write_event(user_id: str, event_name: str, properties: dict) -> None:
    """Fire-and-forget DB write — swallows all errors so callers are never blocked."""
    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO analytics_event (user_id, event_name, properties_json) "
                "VALUES (%s, %s, %s)",
                (user_id, event_name, json.dumps(properties, ensure_ascii=False)),
            )
    except Exception:
        _logger.warning("analytics: failed to write event %s for user %s", event_name, user_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/event", status_code=202)
def track_event(
    body: EventBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Record one analytics event (fire-and-forget, never blocks the caller)."""
    background_tasks.add_task(_write_event, user["id"], body.event, body.properties)
    return {"queued": True}


@router.get("/outreach-funnel")
def outreach_funnel(
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Return outreach conversion funnel metrics. Admin only."""
    _require_admin(user)

    with transaction() as cur:
        cur.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM outreach_log
            WHERE created_at >= NOW() - %s * INTERVAL '1 day'
            GROUP BY status
            """,
            (days,),
        )
        rows = cur.fetchall()

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = int(r["cnt"])

    draft_count = counts.get("draft", 0)
    sent_count = counts.get("sent", 0)
    # 'meeting' is a reply-stage milestone — count it with replied
    replied_count = counts.get("replied", 0) + counts.get("meeting", 0)
    signed_count = counts.get("cda_signed", 0) + counts.get("ts_signed", 0)
    dropped_count = counts.get("passed", 0) + counts.get("dead", 0)

    def _rate(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 0.0

    return {
        "draft_count": draft_count,
        "sent_count": sent_count,
        "replied_count": replied_count,
        "signed_count": signed_count,
        "dropped_count": dropped_count,
        "draft_to_sent_rate": _rate(sent_count, draft_count + sent_count),
        "sent_to_replied_rate": _rate(replied_count, sent_count),
        "replied_to_signed_rate": _rate(signed_count, replied_count),
        "window_days": days,
    }


@router.get("/slash-usage")
def slash_usage(
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Return per-slug report generation counts from report_history. Admin only."""
    _require_admin(user)

    with transaction() as cur:
        cur.execute(
            """
            SELECT slug, COUNT(*) AS cnt
            FROM report_history
            WHERE created_at >= NOW() - %s * INTERVAL '1 day'
            GROUP BY slug
            ORDER BY cnt DESC
            """,
            (days,),
        )
        rows = cur.fetchall()

    return {
        "data": [{"slug": r["slug"], "count": int(r["cnt"])} for r in rows],
        "window_days": days,
    }
