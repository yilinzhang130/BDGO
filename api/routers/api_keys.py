"""
routers/api_keys.py — Self-service API key management for developers.

All endpoints require JWT (browser session) — there is intentionally no
``@public_api`` marker here. Issuing a new key via an existing API key would
be a privilege-escalation primitive.

Endpoints::

    GET    /api/keys              list the caller's keys (no secrets)
    POST   /api/keys              create a new key (returns secret once)
    DELETE /api/keys/{key_id}     revoke a key

The raw secret is returned *only* from POST. List/get never include it.
"""

from __future__ import annotations

import api_keys as api_keys_mod
import api_request_log as api_request_log_mod
from auth import get_current_user
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User-facing label")
    scopes: list[str] = Field(default_factory=list, description="Reserved — currently unused")
    quota_daily: int | None = Field(
        None, gt=0, description="Max requests/day (None = inherit default)"
    )


class CreateKeyResponse(BaseModel):
    """Includes the one-time raw ``key`` value. The caller MUST save it —
    there's no way to recover it later (only its sha256 hash is stored)."""

    key: str
    record: dict


class KeyRecord(BaseModel):
    id: str
    user_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    quota_daily: int | None
    created_at: str
    last_used_at: str | None
    last_used_ip: str | None = None
    revoked_at: str | None
    expires_at: str | None
    is_active: bool


class KeyListResponse(BaseModel):
    items: list[KeyRecord]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=KeyListResponse)
def list_my_keys(
    include_revoked: bool = False,
    user: dict = Depends(get_current_user),
):
    """List all API keys owned by the current user.

    Revoked keys are hidden by default — pass ``?include_revoked=true`` to
    see the full audit history.
    """
    return {"items": api_keys_mod.list_keys(user["id"], include_revoked=include_revoked)}


@router.post("", response_model=CreateKeyResponse)
def create_my_key(
    body: CreateKeyRequest,
    user: dict = Depends(get_current_user),
):
    """Issue a new API key. Response includes the raw key value **once**.

    The caller is responsible for persisting it — subsequent reads only
    return the hashed record.
    """
    return api_keys_mod.create_key(
        user_id=user["id"],
        name=body.name,
        scopes=body.scopes,
        quota_daily=body.quota_daily,
    )


@router.delete("/{key_id}", response_model=dict)
def revoke_my_key(
    key_id: str,
    user: dict = Depends(get_current_user),
):
    """Revoke a key the caller owns. Returns 404 for unknown / already-revoked
    keys so the UI can distinguish 'never existed' from 'already done'."""
    return api_keys_mod.revoke_key(user_id=user["id"], key_id=key_id)


@router.get("/usage/recent", response_model=dict)
def my_recent_usage(
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """Recent API calls made with any of the caller's keys (newest first).

    Powers the developer-portal usage tab. JWT-only — same key can't be
    used to peek at its own call history (that would be weird recursion).
    """
    return {"items": api_request_log_mod.recent_for_user(user["id"], limit=limit)}
