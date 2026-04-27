"""Sell-side workspace endpoints (Phase 2, P2-1).

Backs the new /sell workspace. The "sell-side asset" concept is a thin
projection over existing data:
  - The asset list = the user's watchlist entries with entity_type='asset'.
    Phase 2 PR 9 will add an explicit ``selling=True`` flag if we ever
    need to distinguish "watching" from "selling" — for now, every
    watchlisted asset is treated as a sell-side candidate.
  - For each asset we augment with:
      * outreach_count    — how many outreach events touch this asset
                            (best-effort match on outreach_log.asset_context)
      * last_outreach_at  — most-recent outreach timestamp
      * crm_metadata      — phase / target / indication, if the name
                            resolves in the CRM assets table

The page does not yet write any state — all CRUD on the underlying
watchlist row goes through /api/watchlist (existing).
"""

from __future__ import annotations

from auth import get_current_user
from auth_db import transaction
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/sell/assets
# ---------------------------------------------------------------------------


@router.get("/assets")
def list_sell_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Return the user's sell-side assets with outreach + CRM augmentation.

    Source of truth for the list is ``user_watchlists`` filtered to
    entity_type='asset'. Each row is augmented with two server-computed
    columns so the workspace card can render without N+1 client calls.
    """
    offset = (page - 1) * page_size
    user_id = user["id"]

    with transaction() as cur:
        # Total count for pagination
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_watchlists "
            "WHERE user_id = %s AND entity_type = 'asset'",
            (user_id,),
        )
        total = cur.fetchone()["cnt"]

        # Page of assets, newest first
        cur.execute(
            "SELECT id, entity_key, notes, added_at "
            "FROM user_watchlists "
            "WHERE user_id = %s AND entity_type = 'asset' "
            "ORDER BY added_at DESC LIMIT %s OFFSET %s",
            (user_id, page_size, offset),
        )
        rows = cur.fetchall()

        # Outreach augmentation: count + last_touched per asset_context.
        # asset_context is free-text in outreach_log so we match by
        # case-insensitive substring on the watchlist entity_key.
        # This is intentionally best-effort — Phase 2 PR 9 adds a real
        # asset_id FK so this guesswork goes away.
        augmented: list[dict] = []
        for row in rows:
            key = row["entity_key"]
            cur.execute(
                "SELECT COUNT(*) AS cnt, MAX(created_at) AS last_at "
                "FROM outreach_log "
                "WHERE user_id = %s AND asset_context ILIKE %s",
                (user_id, f"%{key}%"),
            )
            stats = cur.fetchone() or {}
            last_at = stats.get("last_at")
            augmented.append(
                {
                    "id": row["id"],
                    "entity_key": key,
                    "notes": row["notes"],
                    "added_at": row["added_at"].isoformat() if row["added_at"] else None,
                    "outreach_count": int(stats.get("cnt") or 0),
                    "last_outreach_at": last_at.isoformat() if last_at else None,
                    # CRM metadata enrichment is left to a future PR — the
                    # CRM "assets" table is a global library and joining
                    # by free-text name produces too many false positives
                    # to be useful without canonicalisation.
                    "crm_metadata": None,
                }
            )

    return {
        "data": augmented,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, -(-total // page_size)),
    }


# ---------------------------------------------------------------------------
# Single-asset detail endpoint — backs the /sell/[assetId] workspace
# ---------------------------------------------------------------------------


@router.get("/assets/{asset_id}")
def get_sell_asset(asset_id: int, user: dict = Depends(get_current_user)):
    """Return a single sell-side asset with full augmentation.

    Used by the /sell/[assetId] detail page (P2-2). Same shape as one
    item in the list endpoint, plus a recent-outreach preview (5 events)
    and a placeholder ``timeline`` array the Overview tab can render
    without a second round-trip.
    """
    user_id = user["id"]
    with transaction() as cur:
        cur.execute(
            "SELECT id, entity_key, notes, added_at "
            "FROM user_watchlists "
            "WHERE id = %s AND user_id = %s AND entity_type = 'asset'",
            (asset_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Sell-side asset not found")

        key = row["entity_key"]

        # Outreach stats — same best-effort match as the list endpoint.
        cur.execute(
            "SELECT COUNT(*) AS cnt, MAX(created_at) AS last_at "
            "FROM outreach_log "
            "WHERE user_id = %s AND asset_context ILIKE %s",
            (user_id, f"%{key}%"),
        )
        stats = cur.fetchone() or {}

        # Recent outreach preview — keep it small (5) so the Overview
        # tab can render without paginating; full pipeline lives at
        # /outreach.
        cur.execute(
            "SELECT id, to_company, to_contact, status, purpose, "
            "subject, created_at "
            "FROM outreach_log "
            "WHERE user_id = %s AND asset_context ILIKE %s "
            "ORDER BY created_at DESC LIMIT 5",
            (user_id, f"%{key}%"),
        )
        recent = cur.fetchall() or []

    last_at = stats.get("last_at")
    return {
        "id": row["id"],
        "entity_key": key,
        "notes": row["notes"],
        "added_at": row["added_at"].isoformat() if row["added_at"] else None,
        "outreach_count": int(stats.get("cnt") or 0),
        "last_outreach_at": last_at.isoformat() if last_at else None,
        "crm_metadata": None,
        "recent_outreach": [
            {
                "id": r["id"],
                "to_company": r["to_company"],
                "to_contact": r.get("to_contact"),
                "status": r["status"],
                "purpose": r["purpose"],
                "subject": r.get("subject"),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else "",
            }
            for r in recent
        ],
    }
