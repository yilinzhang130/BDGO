"""
Sessions API router — CRUD for chat sessions, messages, and context entities.

All endpoints are user-scoped via the auth dependency applied in main.py.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from auth import get_current_user
from auth_db import transaction
from crm_store import like_contains
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateSessionBody(BaseModel):
    title: str = "New Chat"


class RenameSessionBody(BaseModel):
    title: str


class AddMessageBody(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: Literal["user", "assistant", "system"]
    content: str = ""
    tools_json: str | None = None
    attachments_json: str | None = None


class UpsertEntityBody(BaseModel):
    id: str
    entity_type: str
    title: str
    subtitle: str | None = None
    fields_json: str | None = None
    href: str | None = None


# Response models — frontend translates these via mapServerSession /
# mapServerSessionSummary (see frontend/src/lib/sessions.ts).


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class SessionMessage(BaseModel):
    id: str
    role: str
    content: str
    tools_json: str | None = None
    attachments_json: str | None = None
    created_at: str


class SessionEntity(BaseModel):
    id: str
    entity_type: str
    title: str
    subtitle: str | None = None
    fields_json: str | None = None
    href: str | None = None
    added_at: str


class SessionDetail(SessionSummary):
    messages: list[SessionMessage] = []
    context_entities: list[SessionEntity] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def _verify_owner(cur, session_id: str, user_id: str) -> dict:
    """Return the session row if *user_id* owns it, else raise 404.

    Uses the caller's cursor so the check runs inside the same transaction.
    """
    cur.execute(
        "SELECT id, user_id, title, created_at, updated_at FROM sessions WHERE id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    if not row or str(row["user_id"]) != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(row)


def _serialize_row(row: dict) -> dict:
    """Stringify datetime / UUID fields for JSON."""
    out = dict(row)
    for k in ("created_at", "updated_at", "added_at", "user_id"):
        if k in out and out[k] is not None:
            out[k] = str(out[k])
    return out


# ---------------------------------------------------------------------------
# 1. GET /api/sessions
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SessionSummary])
def list_sessions(user: dict = Depends(get_current_user)):
    with transaction() as cur:
        cur.execute(
            "SELECT id, title, created_at, updated_at "
            "FROM sessions WHERE user_id = %s "
            "ORDER BY updated_at DESC LIMIT 50",
            (user["id"],),
        )
        rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Search sessions by title or message content
# ---------------------------------------------------------------------------


@router.get("/search")
def search_sessions(q: str = "", limit: int = 6, user: dict = Depends(get_current_user)):
    """Search chat sessions by title or message content."""
    user_id = user["id"]
    with transaction() as cur:
        if q:
            # EXISTS avoids scanning all messages per session (vs unbounded LEFT JOIN)
            pat = like_contains(q)
            cur.execute(
                r"""SELECT s.id, s.title, s.updated_at
                    FROM sessions s
                    WHERE s.user_id = %s
                      AND (s.title ILIKE %s ESCAPE '\'
                           OR EXISTS (
                               SELECT 1 FROM messages m
                               WHERE m.session_id = s.id AND m.content ILIKE %s ESCAPE '\'
                               LIMIT 1
                           ))
                    ORDER BY s.updated_at DESC
                    LIMIT %s""",
                (user_id, pat, pat, limit),
            )
        else:
            cur.execute(
                "SELECT id, title, updated_at FROM sessions WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
                (user_id, limit),
            )
        rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


# ---------------------------------------------------------------------------
# 2. POST /api/sessions
# ---------------------------------------------------------------------------


@router.post("")
def create_session(body: CreateSessionBody, user: dict = Depends(get_current_user)):
    sid = _gen_id()
    with transaction() as cur:
        cur.execute(
            "INSERT INTO sessions (id, user_id, title) "
            "VALUES (%s, %s, %s) RETURNING id, title, created_at, updated_at",
            (sid, user["id"], body.title),
        )
        row = cur.fetchone()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 3. GET /api/sessions/{session_id}
# ---------------------------------------------------------------------------


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, user: dict = Depends(get_current_user)):
    with transaction() as cur:
        session = _verify_owner(cur, session_id, user["id"])

        # P-014: Limit to the 200 most recent messages to keep response size
        # bounded.  The frontend holds prior messages in its own state, so
        # re-fetching only the tail is safe for resumed sessions.
        cur.execute(
            "SELECT id, role, content, tools_json, attachments_json, created_at "
            "FROM messages WHERE session_id = %s "
            "ORDER BY created_at DESC LIMIT 200",
            (session_id,),
        )
        messages = [_serialize_row(r) for r in reversed(cur.fetchall())]

        cur.execute(
            "SELECT id, entity_type, title, subtitle, fields_json, href, added_at "
            "FROM context_entities WHERE session_id = %s ORDER BY added_at ASC",
            (session_id,),
        )
        entities = [_serialize_row(r) for r in cur.fetchall()]

    result = _serialize_row(session)
    result["messages"] = messages
    result["context_entities"] = entities
    return result


# ---------------------------------------------------------------------------
# 4. PUT /api/sessions/{session_id}
# ---------------------------------------------------------------------------


@router.put("/{session_id}")
def rename_session(
    session_id: str, body: RenameSessionBody, user: dict = Depends(get_current_user)
):
    with transaction() as cur:
        _verify_owner(cur, session_id, user["id"])
        cur.execute(
            "UPDATE sessions SET title = %s, updated_at = NOW() "
            "WHERE id = %s RETURNING id, title, created_at, updated_at",
            (body.title, session_id),
        )
        row = cur.fetchone()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 5. DELETE /api/sessions/{session_id}
# ---------------------------------------------------------------------------


@router.delete("/{session_id}")
def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    with transaction() as cur:
        _verify_owner(cur, session_id, user["id"])
        cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    return {"ok": True}


# ---------------------------------------------------------------------------
# 6. POST /api/sessions/{session_id}/messages
# ---------------------------------------------------------------------------


@router.post("/{session_id}/messages")
def add_message(session_id: str, body: AddMessageBody, user: dict = Depends(get_current_user)):
    with transaction() as cur:
        _verify_owner(cur, session_id, user["id"])
        cur.execute(
            "INSERT INTO messages (id, session_id, role, content, tools_json, attachments_json) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "RETURNING id, role, content, tools_json, attachments_json, created_at",
            (body.id, session_id, body.role, body.content, body.tools_json, body.attachments_json),
        )
        row = cur.fetchone()
        cur.execute(
            "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
            (session_id,),
        )
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 7. POST /api/sessions/{session_id}/entities
# ---------------------------------------------------------------------------


@router.post("/{session_id}/entities")
def upsert_entity(session_id: str, body: UpsertEntityBody, user: dict = Depends(get_current_user)):
    with transaction() as cur:
        _verify_owner(cur, session_id, user["id"])
        cur.execute(
            """INSERT INTO context_entities (id, session_id, entity_type, title, subtitle, fields_json, href)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET
                   entity_type = EXCLUDED.entity_type,
                   title = EXCLUDED.title,
                   subtitle = EXCLUDED.subtitle,
                   fields_json = EXCLUDED.fields_json,
                   href = EXCLUDED.href,
                   added_at = NOW()
               RETURNING id, entity_type, title, subtitle, fields_json, href, added_at""",
            (
                body.id,
                session_id,
                body.entity_type,
                body.title,
                body.subtitle,
                body.fields_json,
                body.href,
            ),
        )
        row = cur.fetchone()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 8. DELETE /api/sessions/{session_id}/entities/{entity_id}
# ---------------------------------------------------------------------------


@router.delete("/{session_id}/entities/{entity_id}")
def delete_entity(session_id: str, entity_id: str, user: dict = Depends(get_current_user)):
    with transaction() as cur:
        _verify_owner(cur, session_id, user["id"])
        cur.execute(
            "DELETE FROM context_entities WHERE id = %s AND session_id = %s",
            (entity_id, session_id),
        )
        deleted = cur.rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"ok": True}
