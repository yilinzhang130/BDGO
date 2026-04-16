"""
Admin endpoints — user management, invite codes, credit grants.

Dual auth: X-Admin-Key header (for curl/scripts) OR JWT with is_admin=True (for UI).
"""

from __future__ import annotations

import os
import random
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import transaction
from auth import get_current_user, serialize_user_row
from field_policy import is_admin_user
import credits as credits_mod

router = APIRouter()

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def _check_admin(x_admin_key: str = Header(...)):
    """Header-key auth for curl/scripts."""
    if not ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="Admin not configured (ADMIN_SECRET not set)")
    if x_admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def _require_admin(user: dict = Depends(get_current_user)) -> dict:
    """JWT-based admin check for frontend."""
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="管理员权限不足")
    return user


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


def _fmt(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "code": row["code"],
        "note": row.get("note"),
        "max_uses": row["max_uses"],
        "use_count": row["use_count"],
        "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.post("/invite-codes")
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

def _set_admin_flag(email: str, value: bool) -> dict:
    with transaction() as cur:
        cur.execute(
            "UPDATE users SET is_admin = %s WHERE email = %s RETURNING id, email, name",
            (value, email.lower().strip()),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"User not found: {email}")
    return {"ok": True, "email": row["email"], "name": row["name"], "is_admin": value}


@router.post("/users/{email}/set-admin")
def set_user_admin(email: str, x_admin_key: str = Header(...)):
    _check_admin(x_admin_key)
    return _set_admin_flag(email, True)


@router.post("/users/{email}/revoke-admin")
def revoke_user_admin(email: str, x_admin_key: str = Header(...)):
    _check_admin(x_admin_key)
    return _set_admin_flag(email, False)


@router.get("/users")
def list_users(x_admin_key: str = Header(...)):
    """List all registered users (X-Admin-Key auth)."""
    _check_admin(x_admin_key)

    with transaction() as cur:
        cur.execute(
            "SELECT id, email, name, is_admin, created_at, last_login, company "
            "FROM users ORDER BY created_at DESC"
        )
        rows = [dict(r) for r in cur.fetchall()]

    return {"users": [serialize_user_row(r) for r in rows]}


# ---------------------------------------------------------------------------
# JWT-authenticated endpoints (for frontend admin dashboard)
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def admin_dashboard(_: dict = Depends(_require_admin)):
    """Users + credit balances for admin UI."""
    with transaction() as cur:
        cur.execute("""
            SELECT u.id, u.email, u.name, u.is_admin, u.is_active, u.is_internal,
                   u.company, u.title, u.created_at, u.last_login,
                   COALESCE(c.balance, 0) AS credit_balance,
                   COALESCE(c.total_granted, 0) AS total_granted,
                   COALESCE(c.total_spent, 0) AS total_spent
            FROM users u
            LEFT JOIN credits c ON c.user_id = u.id
            ORDER BY u.created_at DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]

    users = []
    for r in rows:
        u = serialize_user_row(r)
        u["credit_balance"] = float(r["credit_balance"])
        u["total_granted"] = float(r["total_granted"])
        u["total_spent"] = float(r["total_spent"])
        users.append(u)

    return {"users": users}


class SetFlagBody(BaseModel):
    user_id: str
    value: bool


@router.post("/users/set-active-ui")
def set_user_active(body: SetFlagBody, admin: dict = Depends(_require_admin)):
    """Ban/unban a user (JWT auth)."""
    if body.user_id == admin["id"] and body.value is False:
        raise HTTPException(400, "不能停用自己的账户")
    with transaction() as cur:
        cur.execute(
            "UPDATE users SET is_active = %s WHERE id = %s RETURNING id, email, is_active",
            (body.value, body.user_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {"ok": True, "user_id": str(row["id"]), "is_active": row["is_active"]}


@router.post("/users/set-admin-ui")
def set_user_admin_ui(body: SetFlagBody, admin: dict = Depends(_require_admin)):
    """Grant/revoke admin flag (JWT auth)."""
    if body.user_id == admin["id"] and body.value is False:
        raise HTTPException(400, "不能撤销自己的管理员权限")
    with transaction() as cur:
        cur.execute(
            "UPDATE users SET is_admin = %s WHERE id = %s RETURNING id, email, is_admin",
            (body.value, body.user_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {"ok": True, "user_id": str(row["id"]), "is_admin": row["is_admin"]}


@router.post("/users/set-internal-ui")
def set_user_internal_ui(body: SetFlagBody, _: dict = Depends(_require_admin)):
    """Mark user as internal (sees subjective fields) or external (stripped)."""
    with transaction() as cur:
        cur.execute(
            "UPDATE users SET is_internal = %s WHERE id = %s RETURNING id, email, is_internal",
            (body.value, body.user_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {"ok": True, "user_id": str(row["id"]), "is_internal": row["is_internal"]}


class GrantCreditsUI(BaseModel):
    user_id: str
    amount: float


@router.post("/credits/grant-ui")
def admin_grant_credits_ui(body: GrantCreditsUI, admin: dict = Depends(_require_admin)):
    """Grant credits (JWT auth for frontend)."""
    if body.amount <= 0:
        raise HTTPException(400, "amount 必须大于 0")
    return credits_mod.grant_credits(body.user_id, body.amount, f"granted by {admin['email']}")


@router.get("/invite-codes-ui")
def list_invite_codes_ui(_: dict = Depends(_require_admin)):
    """List invite codes (JWT auth for frontend)."""
    with transaction() as cur:
        cur.execute("SELECT * FROM invite_codes ORDER BY created_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
    return {"codes": [_fmt(r) for r in rows]}


class CreateCodeUI(BaseModel):
    max_uses: int = 1


@router.post("/invite-codes-ui")
def create_invite_code_ui(body: CreateCodeUI, _: dict = Depends(_require_admin)):
    """Create invite code (JWT auth for frontend)."""
    code = _random_code()
    with transaction() as cur:
        cur.execute(
            "INSERT INTO invite_codes (code, max_uses) VALUES (%s, %s) RETURNING *",
            (code, body.max_uses),
        )
        row = dict(cur.fetchone())
    return _fmt(row)


@router.delete("/invite-codes-ui/{code}")
def delete_invite_code_ui(code: str, _: dict = Depends(_require_admin)):
    """Revoke invite code (JWT auth for frontend)."""
    with transaction() as cur:
        cur.execute("DELETE FROM invite_codes WHERE code = %s RETURNING id", (code.upper(),))
        deleted = cur.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Code not found")
    return {"deleted": True, "code": code.upper()}
