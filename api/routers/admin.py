"""
Admin endpoints — invite code management.

All endpoints require X-Admin-Key header matching ADMIN_SECRET env var.
"""

from __future__ import annotations

import os
import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database import transaction

router = APIRouter()

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def _check_admin(x_admin_key: str = Header(...)):
    if not ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="Admin not configured (ADMIN_SECRET not set)")
    if x_admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def _random_code() -> str:
    """Generate a code like BDGO-A3K9-X7M2"""
    chars = string.ascii_uppercase + string.digits
    part = lambda n: "".join(random.choices(chars, k=n))
    return f"BDGO-{part(4)}-{part(4)}"


class CreateCodeRequest(BaseModel):
    note: str | None = None
    max_uses: int = 1
    expires_days: int | None = None  # None = never expires
    code: str | None = None          # custom code; auto-generated if omitted


class CodeResponse(BaseModel):
    id: int
    code: str
    note: str | None
    max_uses: int
    use_count: int
    expires_at: str | None
    created_at: str


def _fmt(row: dict) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "note": row.get("note"),
        "max_uses": row["max_uses"],
        "use_count": row["use_count"],
        "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.post("/invite-codes", response_model=CodeResponse)
def create_invite_code(body: CreateCodeRequest, x_admin_key: str = Header(...)):
    _check_admin(x_admin_key)

    code = (body.code or _random_code()).strip().upper()
    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)

    with transaction() as cur:
        cur.execute(
            "INSERT INTO invite_codes (code, note, max_uses, expires_at) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (code, body.note, body.max_uses, expires_at),
        )
        row = dict(cur.fetchone())

    return _fmt(row)


@router.get("/invite-codes")
def list_invite_codes(x_admin_key: str = Header(...)):
    _check_admin(x_admin_key)

    with transaction() as cur:
        cur.execute("SELECT * FROM invite_codes ORDER BY created_at DESC")
        rows = [dict(r) for r in cur.fetchall()]

    return {"codes": [_fmt(r) for r in rows]}


@router.delete("/invite-codes/{code}")
def revoke_invite_code(code: str, x_admin_key: str = Header(...)):
    _check_admin(x_admin_key)

    with transaction() as cur:
        cur.execute("DELETE FROM invite_codes WHERE code = %s RETURNING id", (code.upper(),))
        deleted = cur.fetchone()

    if not deleted:
        raise HTTPException(status_code=404, detail="Code not found")
    return {"deleted": True, "code": code.upper()}


# ---------------------------------------------------------------------------
# User admin management
# ---------------------------------------------------------------------------

@router.post("/users/{email}/set-admin")
def set_user_admin(email: str, x_admin_key: str = Header(...)):
    """Grant admin privileges to a user by email."""
    _check_admin(x_admin_key)

    with transaction() as cur:
        cur.execute(
            "UPDATE users SET is_admin = TRUE WHERE email = %s RETURNING id, email, name",
            (email.lower().strip(),),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"User not found: {email}")
    return {"ok": True, "email": row["email"], "name": row["name"], "is_admin": True}


@router.post("/users/{email}/revoke-admin")
def revoke_user_admin(email: str, x_admin_key: str = Header(...)):
    """Revoke admin privileges from a user by email."""
    _check_admin(x_admin_key)

    with transaction() as cur:
        cur.execute(
            "UPDATE users SET is_admin = FALSE WHERE email = %s RETURNING id, email, name",
            (email.lower().strip(),),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"User not found: {email}")
    return {"ok": True, "email": row["email"], "name": row["name"], "is_admin": False}


@router.get("/users")
def list_users(x_admin_key: str = Header(...)):
    """List all registered users."""
    _check_admin(x_admin_key)

    with transaction() as cur:
        cur.execute(
            "SELECT id, email, name, is_admin, created_at, last_login, company "
            "FROM users ORDER BY created_at DESC"
        )
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r["id"] = str(r["id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("last_login"):
            r["last_login"] = r["last_login"].isoformat()

    return {"users": rows}
