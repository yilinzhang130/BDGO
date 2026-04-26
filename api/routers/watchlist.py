"""Watchlist endpoints — per-user entity favorites (company/asset/disease/target).

Also includes sharing endpoints (P3-14):
  POST   /api/watchlist/{id}/share          — share item with a teammate
  GET    /api/watchlist/shared              — items shared with me
  DELETE /api/watchlist/{id}/share/{uid}    — remove a share
"""

from auth import get_current_user
from auth_db import transaction
from crm_store import like_contains
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from routers.team import send_notification

router = APIRouter()

VALID_ENTITY_TYPES = {"company", "asset", "disease", "target", "incubator"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WatchlistAdd(BaseModel):
    entity_type: str
    # M-027: max_length guards against an LLM tool call passing an arbitrarily
    # long string that would overflow the DB column or spike memory.
    entity_key: str = Field(..., max_length=500)
    notes: str | None = Field(None, max_length=2000)


class WatchlistCheckResponse(BaseModel):
    watched: bool
    id: int | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_watchlist(
    type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Return the current user's watchlist with optional filters."""
    conditions = ["user_id = %s"]
    params: list = [user["id"]]

    if type:
        # A-002: Reject unknown type values rather than silently ignoring them.
        # POST /watchlist raises 400 for invalid entity_type; GET should be consistent.
        if type not in VALID_ENTITY_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid type filter. Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
            )
        conditions.append("entity_type = %s")
        params.append(type)

    if q:
        conditions.append("entity_key ILIKE %s ESCAPE '\\'")
        params.append(like_contains(q))

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with transaction() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM user_watchlists WHERE {where}", tuple(params))
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"SELECT id, entity_type, entity_key, notes, added_at "
            f"FROM user_watchlists WHERE {where} "
            f"ORDER BY added_at DESC LIMIT %s OFFSET %s",
            (*params, page_size, offset),
        )
        rows = cur.fetchall()

    data = [
        {
            "id": r["id"],
            "entity_type": r["entity_type"],
            "entity_key": r["entity_key"],
            "notes": r["notes"],
            "added_at": r["added_at"].isoformat() if r["added_at"] else None,
        }
        for r in rows
    ]

    return {
        "data": data,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.post("", status_code=201)
def add_to_watchlist(body: WatchlistAdd, user: dict = Depends(get_current_user)):
    """Add an entity to the user's watchlist."""
    if body.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            400, f"Invalid entity_type. Must be one of: {', '.join(VALID_ENTITY_TYPES)}"
        )

    entity_key = body.entity_key.strip()
    if not entity_key:
        raise HTTPException(400, "entity_key cannot be empty")

    with transaction() as cur:
        cur.execute(
            "INSERT INTO user_watchlists (user_id, entity_type, entity_key, notes) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (user_id, entity_type, entity_key) DO UPDATE SET notes = EXCLUDED.notes "
            "RETURNING id, entity_type, entity_key, notes, added_at",
            (user["id"], body.entity_type, entity_key, body.notes),
        )
        row = cur.fetchone()

    return {
        "id": row["id"],
        "entity_type": row["entity_type"],
        "entity_key": row["entity_key"],
        "notes": row["notes"],
        "added_at": row["added_at"].isoformat() if row["added_at"] else None,
    }


@router.delete("/{item_id}")
def remove_from_watchlist(item_id: int, user: dict = Depends(get_current_user)):
    """Remove an item from the user's watchlist."""
    with transaction() as cur:
        cur.execute(
            "DELETE FROM user_watchlists WHERE id = %s AND user_id = %s RETURNING id",
            (item_id, user["id"]),
        )
        deleted = cur.fetchone()

    if not deleted:
        raise HTTPException(404, "Watchlist item not found")
    return {"deleted": True}


@router.get("/check", response_model=WatchlistCheckResponse)
def check_watchlist(
    entity_type: str = Query(...),
    entity_key: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Check if an entity is in the user's watchlist."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            400, f"Invalid entity_type. Must be one of: {', '.join(VALID_ENTITY_TYPES)}"
        )

    with transaction() as cur:
        cur.execute(
            "SELECT id FROM user_watchlists "
            "WHERE user_id = %s AND entity_type = %s AND entity_key = %s",
            (user["id"], entity_type, entity_key.strip()),
        )
        row = cur.fetchone()

    if row:
        return {"watched": True, "id": row["id"]}
    return {"watched": False}


# ---------------------------------------------------------------------------
# Sharing models
# ---------------------------------------------------------------------------


class ShareRequest(BaseModel):
    user_id: str  # UUID of the teammate to share with
    permission: str = "view"  # 'view' | 'edit'
    note: str | None = None  # optional message to send as notification


class SharedItemOut(BaseModel):
    share_id: int
    item_id: int
    entity_type: str
    entity_key: str
    notes: str | None
    owner_id: str
    owner_name: str
    owner_email: str
    permission: str
    shared_at: str


# ---------------------------------------------------------------------------
# Share endpoints
# ---------------------------------------------------------------------------


@router.post("/{item_id}/share")
def share_watchlist_item(
    item_id: int,
    body: ShareRequest,
    user: dict = Depends(get_current_user),
):
    """Share a watchlist item with a teammate.  Creates a notification for the recipient."""
    if body.permission not in ("view", "edit"):
        raise HTTPException(400, "permission must be 'view' or 'edit'")

    with transaction() as cur:
        # Verify ownership
        cur.execute(
            "SELECT id, entity_type, entity_key FROM user_watchlists "
            "WHERE id = %s AND user_id = %s",
            (item_id, user["id"]),
        )
        item = cur.fetchone()
        if not item:
            raise HTTPException(404, "Watchlist item not found or not yours")

        # Verify recipient exists
        cur.execute(
            "SELECT id, name FROM users WHERE id = %s AND is_active = TRUE", (body.user_id,)
        )
        recipient = cur.fetchone()
        if not recipient:
            raise HTTPException(404, "Recipient user not found")

        # Upsert share
        cur.execute(
            """
            INSERT INTO watchlist_shares (item_id, owner_id, shared_with_id, permission)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (item_id, shared_with_id) DO UPDATE SET permission = EXCLUDED.permission
            RETURNING id
            """,
            (item_id, user["id"], body.user_id, body.permission),
        )
        share_id = cur.fetchone()["id"]

    # Notify recipient
    sender_name = user.get("name", user.get("email", "Someone"))
    entity_label = f"{item['entity_type']}: {item['entity_key']}"
    note_suffix = f" — {body.note}" if body.note else ""
    send_notification(
        recipient_id=body.user_id,
        sender_id=user["id"],
        type_="watchlist_share",
        title=f"{sender_name} shared a watchlist item with you",
        body=f"{entity_label}{note_suffix}",
        link_url="/watchlist?tab=shared",
    )

    return {"share_id": share_id, "ok": True}


@router.get("/shared", response_model=list[SharedItemOut])
def get_shared_with_me(user: dict = Depends(get_current_user)):
    """Return watchlist items that teammates have shared with the current user."""
    with transaction() as cur:
        cur.execute(
            """
            SELECT ws.id AS share_id,
                   w.id  AS item_id,
                   w.entity_type,
                   w.entity_key,
                   w.notes,
                   ws.owner_id::text,
                   u.name  AS owner_name,
                   u.email AS owner_email,
                   ws.permission,
                   ws.created_at::text AS shared_at
            FROM watchlist_shares ws
            JOIN user_watchlists w ON w.id = ws.item_id
            JOIN users u           ON u.id = ws.owner_id
            WHERE ws.shared_with_id = %s
            ORDER BY ws.created_at DESC
            """,
            (user["id"],),
        )
        return [dict(r) for r in cur.fetchall()]


@router.delete("/{item_id}/share/{target_user_id}")
def remove_share(
    item_id: int,
    target_user_id: str,
    user: dict = Depends(get_current_user),
):
    """Remove a share.  Owner can unshare; recipient can remove their own access."""
    with transaction() as cur:
        cur.execute(
            """
            DELETE FROM watchlist_shares
            WHERE item_id = %s
              AND (owner_id = %s OR shared_with_id = %s)
              AND (shared_with_id = %s OR owner_id = %s)
            RETURNING id
            """,
            (item_id, user["id"], user["id"], target_user_id, target_user_id),
        )
        deleted = cur.fetchone()

    if not deleted:
        raise HTTPException(404, "Share not found")
    return {"ok": True}
