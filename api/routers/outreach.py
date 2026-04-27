"""Outreach endpoints — read-write access to the BD outreach event stream.

Backs the new Outreach workspace page (Phase 1, P1-3 / P1-4 / P1-5):
  GET  /api/outreach/pipeline          — per-company status counts
  GET  /api/outreach/events            — paginated event list (filterable)
  GET  /api/outreach/events/{id}       — single event
  POST /api/outreach/events            — log a new event (replaces /log slash)
  DELETE /api/outreach/events/{id}     — remove a mistakenly logged event

The `/outreach` and `/log` slash services keep working through the existing
report-builder path; this router exposes the same data via REST so the
workspace UI does not have to dispatch a fake report task on every render.
"""

from __future__ import annotations

import outreach_db
from auth import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EventOut(BaseModel):
    id: int
    to_company: str
    to_contact: str | None = None
    purpose: str
    channel: str
    status: str
    asset_context: str | None = None
    perspective: str | None = None
    subject: str | None = None
    notes: str | None = None
    session_id: str | None = None
    created_at: str  # ISO-8601


class EventCreate(BaseModel):
    to_company: str = Field(..., min_length=1, max_length=200)
    purpose: str
    channel: str = "email"
    status: str = "sent"
    to_contact: str | None = Field(None, max_length=200)
    asset_context: str | None = Field(None, max_length=2000)
    perspective: str | None = None
    subject: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=4000)
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_event(row: dict) -> dict:
    """Convert a raw DB row into the JSON-safe EventOut shape."""
    ts = row.get("created_at")
    return {
        "id": row["id"],
        "to_company": row["to_company"],
        "to_contact": row.get("to_contact"),
        "purpose": row["purpose"],
        "channel": row["channel"],
        "status": row["status"],
        "asset_context": row.get("asset_context"),
        "perspective": row.get("perspective"),
        "subject": row.get("subject"),
        "notes": row.get("notes"),
        "session_id": row.get("session_id"),
        "created_at": ts.isoformat() if ts else "",
    }


def _validate_enum(value: str | None, allowed: tuple[str, ...], field: str) -> None:
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}={value!r}. Must be one of: {', '.join(allowed)}",
        )


# ---------------------------------------------------------------------------
# Pipeline (per-company aggregation)
# ---------------------------------------------------------------------------


@router.get("/pipeline")
def pipeline(
    recent_days: int | None = Query(None, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Per-company status counts. Mirrors OutreachListService pipeline view."""
    rows = outreach_db.status_counts_per_company(user_id=user["id"], recent_days=recent_days)

    by_company: dict[str, dict] = {}
    for r in rows:
        c = r["to_company"]
        entry = by_company.setdefault(
            c,
            {"company": c, "statuses": {}, "total_events": 0, "last_touched": r["last_touched"]},
        )
        entry["statuses"][r["status"]] = r["n"]
        entry["total_events"] += r["n"]
        if r["last_touched"] > entry["last_touched"]:
            entry["last_touched"] = r["last_touched"]

    ordered = sorted(by_company.values(), key=lambda x: x["last_touched"], reverse=True)
    for entry in ordered:
        lt = entry["last_touched"]
        entry["last_touched"] = lt.isoformat() if lt else ""

    return {
        "data": ordered,
        "company_count": len(ordered),
        "event_count": sum(int(r["n"]) for r in rows),
        "recent_days": recent_days,
    }


# ---------------------------------------------------------------------------
# Event endpoints — list, fetch one, create, remove
# ---------------------------------------------------------------------------


@router.get("/events")
def list_outreach_events(
    company: str | None = Query(None, max_length=200),
    status: str | None = None,
    purpose: str | None = None,
    perspective: str | None = None,
    recent_days: int | None = Query(None, ge=1, le=365),
    search: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Paginated event list. All filters AND-ed; newest first."""
    _validate_enum(status, outreach_db.STATUSES, "status")
    _validate_enum(purpose, outreach_db.PURPOSES, "purpose")
    _validate_enum(perspective, outreach_db.PERSPECTIVES, "perspective")

    offset = (page - 1) * page_size
    total = outreach_db.count_events(
        user_id=user["id"],
        company=company,
        status=status,
        purpose=purpose,
        perspective=perspective,
        recent_days=recent_days,
        search=search,
    )
    rows = outreach_db.list_events(
        user_id=user["id"],
        company=company,
        status=status,
        purpose=purpose,
        perspective=perspective,
        recent_days=recent_days,
        search=search,
        limit=page_size,
        offset=offset,
    )

    return {
        "data": [_serialize_event(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/events/{event_id}")
def get_outreach_event(event_id: int, user: dict = Depends(get_current_user)):
    row = outreach_db.get_event(user["id"], event_id)
    if not row:
        raise HTTPException(404, "Outreach event not found")
    return _serialize_event(row)


@router.post("/events", status_code=201)
def create_outreach_event(body: EventCreate, user: dict = Depends(get_current_user)):
    """Log a new outreach event (manual entry from the workspace page)."""
    _validate_enum(body.status, outreach_db.STATUSES, "status")
    _validate_enum(body.purpose, outreach_db.PURPOSES, "purpose")
    _validate_enum(body.channel, outreach_db.CHANNELS, "channel")
    _validate_enum(body.perspective, outreach_db.PERSPECTIVES, "perspective")

    company = body.to_company.strip()
    if not company:
        raise HTTPException(400, "to_company cannot be empty")

    new_id = outreach_db.insert_event(
        user_id=user["id"],
        to_company=company,
        purpose=body.purpose,
        channel=body.channel,
        status=body.status,
        to_contact=body.to_contact,
        asset_context=body.asset_context,
        perspective=body.perspective,
        subject=body.subject,
        notes=body.notes,
        session_id=body.session_id,
    )
    row = outreach_db.get_event(user["id"], new_id)
    return _serialize_event(row) if row else {"id": new_id}


@router.delete("/events/{event_id}")
def delete_outreach_event(event_id: int, user: dict = Depends(get_current_user)):
    if not outreach_db.delete_event(user["id"], event_id):
        raise HTTPException(404, "Outreach event not found")
    return {"deleted": True}
