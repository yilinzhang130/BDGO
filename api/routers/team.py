"""
Team features router  (P3-14).

Endpoints:
  GET  /api/team/members                    — org members (same email domain)
  GET  /api/team/notifications              — current user's notifications
  GET  /api/team/notifications/unread-count — badge count
  PATCH /api/team/notifications/{id}/read   — mark one read
  PATCH /api/team/notifications/read-all    — mark all read

Helper used by watchlist + reports routers:
  send_notification(recipient_id, sender_id, type_, title, body, link_url)
"""

from __future__ import annotations

import logging

from auth import get_current_user
from auth_db import transaction
from fastapi import APIRouter, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/team", tags=["team"])


# ─────────────────────────────────────────────────────────────
# Public helper — import this from other routers
# ─────────────────────────────────────────────────────────────


def send_notification(
    recipient_id: str,
    sender_id: str | None,
    type_: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> None:
    """Insert a user_notifications row.  Silently logs errors so callers never fail."""
    try:
        with transaction() as cur:
            cur.execute(
                """
                INSERT INTO user_notifications
                    (recipient_id, sender_id, type, title, body, link_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (recipient_id, sender_id, type_, title, body, link_url),
            )
    except Exception as exc:
        logger.error("send_notification failed: %s", exc)


# ─────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────


class MemberOut(BaseModel):
    id: str
    name: str
    email: str
    avatar_url: str | None = None
    title: str | None = None


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str | None = None
    link_url: str | None = None
    sender_name: str | None = None
    sender_avatar: str | None = None
    read_at: str | None = None
    created_at: str


class NotificationsResponse(BaseModel):
    total: int
    unread: int
    items: list[NotificationOut]


class UnreadCountResponse(BaseModel):
    count: int


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────


@router.get("/members", response_model=list[MemberOut])
def list_members(user: dict = Depends(get_current_user)):
    """Return teammates — users sharing the same email domain.

    Falls back to all active non-admin users when the domain has fewer than 3
    members (solo accounts / dev environments).  Excludes the caller.
    """
    email: str = user.get("email", "")
    domain = email.split("@")[-1] if "@" in email else ""

    with transaction() as cur:
        # Try same-domain first
        if domain:
            cur.execute(
                """
                SELECT id::text, name, email, avatar_url, title
                FROM users
                WHERE is_active = TRUE
                  AND id != %s
                  AND email ILIKE %s
                ORDER BY name
                LIMIT 100
                """,
                (user["id"], f"%@{domain}"),
            )
            rows = cur.fetchall()
        else:
            rows = []

        # Fallback: return all active users (small team / dev)
        if len(rows) < 2:
            cur.execute(
                """
                SELECT id::text, name, email, avatar_url, title
                FROM users
                WHERE is_active = TRUE
                  AND id != %s
                ORDER BY name
                LIMIT 100
                """,
                (user["id"],),
            )
            rows = cur.fetchall()

    return [dict(r) for r in rows]


@router.get("/notifications", response_model=NotificationsResponse)
def list_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    user: dict = Depends(get_current_user),
):
    """Return the current user's notifications, newest first."""
    where_extra = "AND n.read_at IS NULL" if unread_only else ""

    with transaction() as cur:
        cur.execute(
            f"""
            SELECT n.id, n.type, n.title, n.body, n.link_url,
                   n.read_at::text, n.created_at::text,
                   s.name AS sender_name, s.avatar_url AS sender_avatar
            FROM user_notifications n
            LEFT JOIN users s ON s.id = n.sender_id
            WHERE n.recipient_id = %s {where_extra}
            ORDER BY n.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (user["id"], limit, offset),
        )
        rows = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_notifications WHERE recipient_id = %s",
            (user["id"],),
        )
        total = cur.fetchone()["cnt"]

        cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_notifications "
            "WHERE recipient_id = %s AND read_at IS NULL",
            (user["id"],),
        )
        unread = cur.fetchone()["cnt"]

    return {"total": total, "unread": unread, "items": [dict(r) for r in rows]}


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def notifications_unread_count(user: dict = Depends(get_current_user)):
    with transaction() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_notifications "
            "WHERE recipient_id = %s AND read_at IS NULL",
            (user["id"],),
        )
        return {"count": cur.fetchone()["cnt"]}


@router.patch("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, user: dict = Depends(get_current_user)):
    with transaction() as cur:
        cur.execute(
            "UPDATE user_notifications SET read_at = NOW() "
            "WHERE id = %s AND recipient_id = %s AND read_at IS NULL",
            (notif_id, user["id"]),
        )
    return {"ok": True}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    with transaction() as cur:
        cur.execute(
            "UPDATE user_notifications SET read_at = NOW() "
            "WHERE recipient_id = %s AND read_at IS NULL",
            (user["id"],),
        )
    return {"ok": True}
