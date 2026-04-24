"""
auth.py — Password hashing, JWT helpers, and FastAPI auth dependencies.

Two authentication methods are supported on protected endpoints:

  1. ``Authorization: Bearer <jwt>`` — browser sessions (issued via login)
  2. ``X-API-Key: bdgo_live_...``   — programmatic access (issued via
     /api/keys). Only accepted on routes marked ``@public_api``.

``get_current_user`` resolves either into the same user dict and attaches
``auth_method`` (``"jwt"`` or ``"api_key"``) so downstream code can branch
on billing / rate-limiting / scope checks.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os

import api_keys as api_keys_mod
import api_request_log as api_request_log_mod
import bcrypt
import config
import jwt
from fastapi import Depends, Header, HTTPException, Request

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches the bcrypt *hashed* value."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_DAYS = 7


def create_token(user_id: str, email: str) -> str:
    """Create a signed JWT valid for 7 days."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": _dt.datetime.now(_dt.UTC) + _dt.timedelta(days=_JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Returns {"user_id": ..., "email": ...}.

    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    return {"user_id": payload["user_id"], "email": payload["email"]}


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def _extract_bearer(authorization: str | None) -> str:
    """Pull the token out of 'Bearer <token>'."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]


def serialize_user_row(row: dict) -> dict:
    """Normalise a Postgres user row into a JSON-safe dict (shared helper)."""
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("last_login"):
        d["last_login"] = d["last_login"].isoformat()
    d.pop("hashed_password", None)
    return d


_USER_COLUMNS = (
    "id, email, name, avatar_url, provider, created_at, last_login, "
    "company, title, phone, bio, preferences_json, is_admin, is_active, is_internal"
)


def _lookup_user(user_id: str) -> dict:
    """Fetch user row from Postgres by id. Returns dict or raises 401."""
    from auth_db import transaction

    with transaction() as cur:
        cur.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    user = serialize_user_row(row)
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="账户已被停用，请联系管理员")
    return user


# ---------------------------------------------------------------------------
# Public-API marker — a sentinel attribute attached by @public_api.
# When auth sees this flag on the resolved route, it permits X-API-Key
# fallback in addition to JWT. Off by default: endpoints are JWT-only.
# ---------------------------------------------------------------------------

PUBLIC_API_ATTR = "__bdgo_public_api__"


def public_api(func):
    """Mark a route handler as accepting ``X-API-Key`` auth in addition to JWT.

    Usage::

        @router.get("/companies")
        @public_api
        def list_companies(...):
            ...

    Only endpoints carrying this marker can be reached with an API key.
    Everything else stays JWT-only, which keeps ``/api/chat``, ``/api/write``,
    ``/api/upload`` etc. firmly inside the browser session boundary.
    """
    setattr(func, PUBLIC_API_ATTR, True)
    return func


def _route_is_public(request: Request | None) -> bool:
    """Return True if the matched route handler is marked @public_api."""
    if request is None:
        return False
    route = request.scope.get("route")
    endpoint = getattr(route, "endpoint", None) if route is not None else None
    return bool(endpoint and getattr(endpoint, PUBLIC_API_ATTR, False))


def _resolve_api_key_user(request: Request | None, x_api_key: str) -> dict:
    """Validate an ``X-API-Key`` and return the owning user's dict.

    Raises 403 if the route isn't ``@public_api`` (key leaks can't reach
    chat/write/admin), 401 on unknown/revoked keys, 429 on daily-quota
    exhaustion.
    """
    if not _route_is_public(request):
        raise HTTPException(
            status_code=403,
            detail="This endpoint does not accept API key authentication",
        )
    client_ip = request.client.host if (request is not None and request.client) else None
    ctx = api_keys_mod.verify_key(x_api_key, client_ip=client_ip)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # quota_daily IS NULL → unlimited (internal/trusted issuance only).
    # Race note: count_today() reads the log table, which the per-request
    # middleware writes to *after* the response. N parallel in-flight calls
    # can each see the same count and over-run the quota by ≤ concurrency-1.
    # Acceptable: cap is a soft monthly-billing guard, not a hard security
    # boundary. Tighten via a counter row on api_keys if precise needed.
    quota = ctx.get("quota_daily")
    if quota is not None and api_request_log_mod.count_today(ctx["key_id"]) >= quota:
        raise HTTPException(
            status_code=429,
            detail=f"API Key 已达今日配额上限（{quota} 次）。UTC 次日 00:00 自动重置。",
        )

    user = _lookup_user(ctx["user_id"])
    user["auth_method"] = "api_key"
    user["api_key_id"] = ctx["key_id"]
    user["api_key_scopes"] = ctx["scopes"]
    user["api_key_quota_daily"] = ctx["quota_daily"]

    # Cross-module contract: middleware in main.py reads these to emit
    # api_request_logs rows after the response.
    if request is not None:
        request.state.api_key_id = ctx["key_id"]
        request.state.api_user_id = ctx["user_id"]
    return user


def get_current_user(
    request: Request = None,
    authorization: str = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict:
    """FastAPI dependency — requires a valid JWT Bearer token OR an API key.

    API key auth only works on routes marked ``@public_api``. On any other
    route a valid key returns 403, forcing programmatic callers to stick to
    the intentionally-opened surface.

    Returns a user dict (augmented with ``auth_method``) or raises 401.
    """
    if x_api_key:
        return _resolve_api_key_user(request, x_api_key)

    token = _extract_bearer(authorization)
    try:
        claims = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    user = _lookup_user(claims["user_id"])
    user["auth_method"] = "jwt"
    return user


def get_optional_user(
    request: Request = None,
    authorization: str = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict | None:
    """Same as get_current_user but returns None when no credentials are
    provided (or any auth path fails) instead of raising 401."""
    if not authorization and not x_api_key:
        return None
    try:
        return get_current_user(request, authorization, x_api_key)
    except HTTPException:
        return None


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency — 403 if the caller is not an admin."""
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ---------------------------------------------------------------------------
# Header-key auth (for curl / scripts that can't carry a JWT)
# ---------------------------------------------------------------------------

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def require_admin_header(x_admin_key: str | None) -> None:
    """Validate an ``X-Admin-Key`` header value against ``ADMIN_SECRET``.

    Accepts ``None`` (missing header) and treats it the same as a wrong
    key — both get 403. Endpoints should declare the header as
    ``Header(None)`` (not ``Header(...)``), otherwise FastAPI rejects
    missing-header requests with 422 before we can raise 403.
    """
    if not _ADMIN_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Admin not configured (ADMIN_SECRET not set)",
        )
    if not x_admin_key or x_admin_key != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")
