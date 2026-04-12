"""
auth.py — Password hashing, JWT helpers, and FastAPI auth dependencies.
"""

from __future__ import annotations

import datetime as _dt
import logging

import bcrypt
import jwt
from fastapi import Header, HTTPException

import config
import database

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
        "exp": _dt.datetime.now(_dt.timezone.utc)
        + _dt.timedelta(days=_JWT_EXPIRY_DAYS),
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


def _lookup_user(user_id: str) -> dict:
    """Fetch user row from Postgres by id. Returns dict or raises 401."""
    from database import transaction
    with transaction() as cur:
        cur.execute(
            "SELECT id, email, name, avatar_url, provider, created_at, last_login, "
            "company, title, phone, bio, preferences_json "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return serialize_user_row(row)


def get_current_user(authorization: str = Header(None)) -> dict:
    """FastAPI dependency — requires a valid Bearer token.

    Returns a user dict or raises HTTPException(401).
    """
    token = _extract_bearer(authorization)
    try:
        claims = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return _lookup_user(claims["user_id"])


def get_optional_user(authorization: str = Header(None)) -> dict | None:
    """FastAPI dependency — same as get_current_user but returns None
    instead of 401 when no token is provided.
    """
    if not authorization:
        return None
    try:
        token = _extract_bearer(authorization)
        claims = decode_token(token)
        return _lookup_user(claims["user_id"])
    except Exception:
        return None
