"""User feedback + data-quality reports → admin inbox."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, require_admin
from database import transaction

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class DataReportRequest(BaseModel):
    entity_type: str          # '公司' | '资产' | '临床' | '交易'
    entity_key: str           # entity name / id shown to user
    entity_url: str = ""      # frontend deep-link
    message: str              # what's wrong


class FeedbackRequest(BaseModel):
    message: str


# ── User-facing endpoints ─────────────────────────────────────────────────────

@router.post("/report")
def submit_data_report(body: DataReportRequest, user: dict = Depends(get_current_user)):
    """Flag a CRM data entry as incorrect or outdated."""
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    with transaction() as cur:
        cur.execute(
            """INSERT INTO inbox_messages
               (type, user_id, user_email, user_name,
                entity_type, entity_key, entity_url, message)
               VALUES ('data_report', %s, %s, %s, %s, %s, %s, %s)""",
            (user["id"], user["email"], user.get("name", ""),
             body.entity_type, body.entity_key, body.entity_url,
             body.message.strip()),
        )
    return {"ok": True}


@router.post("/feedback")
def submit_feedback(body: FeedbackRequest, user: dict = Depends(get_current_user)):
    """Submit general product feedback."""
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    with transaction() as cur:
        cur.execute(
            """INSERT INTO inbox_messages
               (type, user_id, user_email, user_name, message)
               VALUES ('feedback', %s, %s, %s, %s)""",
            (user["id"], user["email"], user.get("name", ""),
             body.message.strip()),
        )
    return {"ok": True}


# ── Admin-only endpoints ──────────────────────────────────────────────────────

@router.get("/admin/messages")
def list_messages(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    _admin: dict = Depends(require_admin),
):
    """Return inbox messages, newest first. Unread messages come first."""
    where = "WHERE read_at IS NULL" if unread_only else ""
    with transaction() as cur:
        cur.execute(
            f"""SELECT id, type, user_email, user_name,
                       entity_type, entity_key, entity_url,
                       message, read_at, created_at
                FROM inbox_messages
                {where}
                ORDER BY read_at NULLS FIRST, created_at DESC
                LIMIT %s OFFSET %s""",
            (limit, offset),
        )
        rows = cur.fetchall()
        cur.execute(
            f"SELECT COUNT(*) AS total FROM inbox_messages {where}"
        )
        total = cur.fetchone()["total"]
    return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/admin/unread-count")
def unread_count(_admin: dict = Depends(require_admin)):
    with transaction() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM inbox_messages WHERE read_at IS NULL"
        )
        return {"count": cur.fetchone()["n"]}


@router.patch("/admin/messages/{msg_id}/read")
def mark_read(msg_id: int, _admin: dict = Depends(require_admin)):
    with transaction() as cur:
        cur.execute(
            "UPDATE inbox_messages SET read_at = NOW() WHERE id = %s",
            (msg_id,),
        )
    return {"ok": True}


@router.patch("/admin/messages/read-all")
def mark_all_read(_admin: dict = Depends(require_admin)):
    with transaction() as cur:
        cur.execute(
            "UPDATE inbox_messages SET read_at = NOW() WHERE read_at IS NULL"
        )
    return {"ok": True}
