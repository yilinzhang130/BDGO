"""Postgres persistence for chat sessions, messages, context entities,
and the compaction brief cache.

Owns every SQL statement that touches the sessions/messages/context_entities
tables for the chat feature. Exceptions are logged (not re-raised) — chat
streaming must degrade gracefully if the DB hiccups.
"""

from __future__ import annotations

import json
import logging
import uuid

from database import transaction

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────

def ensure_session(session_id: str, user_id: str) -> None:
    """Create the session row if it doesn't exist yet."""
    with transaction() as cur:
        cur.execute("SELECT id FROM sessions WHERE id = %s", (session_id,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO sessions (id, user_id, title) VALUES (%s, %s, %s)",
                (session_id, user_id, "New Chat"),
            )


# ─────────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────────

def load_history(session_id: str) -> list[dict]:
    """Load recent messages for a session from Postgres.

    Assistant messages may have content as a JSON-encoded list of content
    blocks (text / tool_use). User messages with tool_results hold a JSON
    list of tool_result blocks. Plan-card placeholder messages (empty
    content + tools_json containing a plan blob) are skipped — they're
    UI-only artifacts; the LLM never needs to see them.

    No hard cap on returned length — :func:`compact_if_needed` in
    ``compaction.py`` decides what to drop or summarize based on token
    budget.
    """
    with transaction() as cur:
        cur.execute(
            "SELECT role, content, tools_json FROM messages "
            "WHERE session_id = %s ORDER BY created_at DESC LIMIT 100",
            (session_id,),
        )
        rows = cur.fetchall()

    # Rows come back newest-first; reverse to chronological order.
    rows.reverse()

    history: list[dict] = []
    for r in rows:
        content = r["content"]
        tools_json = r.get("tools_json")

        # Skip plan placeholders: empty-content assistant with a plan blob.
        if r["role"] == "assistant" and not (content or "").strip() and tools_json:
            try:
                parsed_tools = json.loads(tools_json)
                if isinstance(parsed_tools, dict) and parsed_tools.get("plan"):
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        # Try parsing JSON content (structured content blocks / tool results)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                history.append({"role": r["role"], "content": parsed})
                continue
        except (json.JSONDecodeError, TypeError):
            pass
        history.append({"role": r["role"], "content": content})

    return history


def save_message(
    session_id: str,
    role: str,
    content,
    tools_json: str | None = None,
    attachments_json: str | None = None,
) -> None:
    """Persist a single message to Postgres (and bump session.updated_at)."""
    if isinstance(content, (list, dict)):
        content_str = json.dumps(content, ensure_ascii=False, default=str)
    else:
        content_str = str(content) if content else ""

    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content, tools_json, attachments_json) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (uuid.uuid4().hex[:12], session_id, role, content_str,
                 tools_json, attachments_json),
            )
            cur.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
    except Exception:
        logger.exception("Failed to save message for session %s", session_id)


# ─────────────────────────────────────────────────────────────
# Context entities (Postgres-backed sidebar state)
# ─────────────────────────────────────────────────────────────

def save_entities(session_id: str, entities: list[dict]) -> None:
    """Upsert context entities extracted from tool results.

    This was accidentally orphaned (lost its ``def`` line) in the earlier
    compaction refactor. Restoring it here fixes the silent tail-end
    NameError that every tool-using chat turn was emitting into the
    outer try/except.
    """
    if not entities:
        return
    try:
        with transaction() as cur:
            params = [
                (e.get("id"), session_id, e.get("entity_type", ""),
                 e.get("title", ""), e.get("subtitle"),
                 json.dumps(e.get("fields", []), ensure_ascii=False) if e.get("fields") else None,
                 e.get("href"))
                for e in entities
            ]
            cur.executemany(
                """INSERT INTO context_entities (id, session_id, entity_type, title, subtitle, fields_json, href)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       entity_type = EXCLUDED.entity_type,
                       title = EXCLUDED.title,
                       subtitle = EXCLUDED.subtitle,
                       fields_json = EXCLUDED.fields_json,
                       href = EXCLUDED.href,
                       added_at = NOW()""",
                params,
            )
    except Exception:
        logger.exception("Failed to save entities for session %s", session_id)


# ─────────────────────────────────────────────────────────────
# Session brief (context-compaction cache)
# ─────────────────────────────────────────────────────────────

def get_session_brief(session_id: str) -> tuple[str | None, str | None]:
    """Return (brief_text, brief_ts_iso) for a session, or (None, None)."""
    try:
        with transaction() as cur:
            cur.execute(
                "SELECT brief, brief_ts FROM sessions WHERE id = %s",
                (session_id,),
            )
            row = cur.fetchone()
    except Exception:
        logger.exception("Failed to load session brief")
        return (None, None)
    if not row:
        return (None, None)
    brief = row.get("brief")
    ts = row.get("brief_ts")
    return (brief, ts.isoformat() if ts else None)


def save_session_brief(
    session_id: str,
    brief: str,
    brief_ts: str | None,
) -> None:
    try:
        with transaction() as cur:
            cur.execute(
                "UPDATE sessions SET brief = %s, "
                "brief_ts = COALESCE(%s::timestamp, brief_ts) "
                "WHERE id = %s",
                (brief, brief_ts, session_id),
            )
    except Exception:
        logger.exception("Failed to save session brief")
