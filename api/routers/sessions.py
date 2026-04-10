"""
Sessions API router — CRUD for chat sessions, messages, and context entities.

All endpoints are user-scoped via the auth dependency applied in main.py.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import database
from auth import get_current_user

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
    role: str
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def _verify_owner(session_id: str, user_id: str) -> dict:
    """Return the session row if *user_id* owns it, else 404."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, title, created_at, updated_at "
                "FROM sessions WHERE id = %s",
                (session_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(row["user_id"]) != user_id:
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
# 1. GET /api/sessions — list sessions
# ---------------------------------------------------------------------------

@router.get("")
def list_sessions(user: dict = Depends(get_current_user)):
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at "
                "FROM sessions WHERE user_id = %s "
                "ORDER BY updated_at DESC LIMIT 50",
                (user["id"],),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_serialize_row(r) for r in rows]


# ---------------------------------------------------------------------------
# 2. POST /api/sessions — create session
# ---------------------------------------------------------------------------

@router.post("")
def create_session(body: CreateSessionBody, user: dict = Depends(get_current_user)):
    sid = _gen_id()
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (id, user_id, title) "
                "VALUES (%s, %s, %s) RETURNING id, title, created_at, updated_at",
                (sid, user["id"], body.title),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 3. GET /api/sessions/{session_id} — session + messages + entities
# ---------------------------------------------------------------------------

@router.get("/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_current_user)):
    session = _verify_owner(session_id, user["id"])

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, content, tools_json, attachments_json, created_at "
                "FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,),
            )
            messages = [_serialize_row(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT id, entity_type, title, subtitle, fields_json, href, added_at "
                "FROM context_entities WHERE session_id = %s ORDER BY added_at ASC",
                (session_id,),
            )
            entities = [_serialize_row(r) for r in cur.fetchall()]
    finally:
        conn.close()

    result = _serialize_row(session)
    result["messages"] = messages
    result["context_entities"] = entities
    return result


# ---------------------------------------------------------------------------
# 4. PUT /api/sessions/{session_id} — rename
# ---------------------------------------------------------------------------

@router.put("/{session_id}")
def rename_session(session_id: str, body: RenameSessionBody, user: dict = Depends(get_current_user)):
    _verify_owner(session_id, user["id"])
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET title = %s, updated_at = NOW() "
                "WHERE id = %s RETURNING id, title, created_at, updated_at",
                (body.title, session_id),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 5. DELETE /api/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.delete("/{session_id}")
def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    _verify_owner(session_id, user["id"])
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
# 6. POST /api/sessions/{session_id}/messages
# ---------------------------------------------------------------------------

@router.post("/{session_id}/messages")
def add_message(session_id: str, body: AddMessageBody, user: dict = Depends(get_current_user)):
    _verify_owner(session_id, user["id"])
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content, tools_json, attachments_json) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, role, content, tools_json, attachments_json, created_at",
                (body.id, session_id, body.role, body.content,
                 body.tools_json, body.attachments_json),
            )
            row = cur.fetchone()
            cur.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 7. POST /api/sessions/{session_id}/entities — upsert
# ---------------------------------------------------------------------------

@router.post("/{session_id}/entities")
def upsert_entity(session_id: str, body: UpsertEntityBody, user: dict = Depends(get_current_user)):
    _verify_owner(session_id, user["id"])
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
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
                (body.id, session_id, body.entity_type, body.title,
                 body.subtitle, body.fields_json, body.href),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# 8. DELETE /api/sessions/{session_id}/entities/{entity_id}
# ---------------------------------------------------------------------------

@router.delete("/{session_id}/entities/{entity_id}")
def delete_entity(session_id: str, entity_id: str, user: dict = Depends(get_current_user)):
    _verify_owner(session_id, user["id"])
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM context_entities WHERE id = %s AND session_id = %s",
                (entity_id, session_id),
            )
            deleted = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"ok": True}
