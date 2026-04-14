"""Watchlist endpoints — per-user entity favorites (company/asset/disease/target)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user
from database import transaction

router = APIRouter()

VALID_ENTITY_TYPES = {"company", "asset", "disease", "target", "incubator"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WatchlistAdd(BaseModel):
    entity_type: str
    entity_key: str
    notes: str | None = None


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

    if type and type in VALID_ENTITY_TYPES:
        conditions.append("entity_type = %s")
        params.append(type)

    if q:
        conditions.append("entity_key ILIKE %s")
        params.append(f"%{q}%")

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
        raise HTTPException(400, f"Invalid entity_type. Must be one of: {', '.join(VALID_ENTITY_TYPES)}")

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


@router.get("/check")
def check_watchlist(
    entity_type: str = Query(...),
    entity_key: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Check if an entity is in the user's watchlist."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(400, f"Invalid entity_type. Must be one of: {', '.join(VALID_ENTITY_TYPES)}")

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
