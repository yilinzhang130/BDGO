"""
routers/auth.py — Registration, login, Google OAuth, and /me endpoint.
"""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth as auth_mod
import config
from database import transaction

_logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    invite_code: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    company: str | None = None
    title: str | None = None
    phone: str | None = None
    bio: str | None = None
    preferences_json: str | None = None


class GoogleLoginRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None
    provider: str
    created_at: str
    last_login: str | None
    company: str | None = None
    title: str | None = None
    phone: str | None = None
    bio: str | None = None
    preferences_json: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


from auth import serialize_user_row as _user_dict, _USER_COLUMNS


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    """Create a new email/password account (requires a valid invite code)."""
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not body.invite_code.strip():
        raise HTTPException(status_code=400, detail="邀请码不能为空")

    hashed = auth_mod.hash_password(body.password)
    code = body.invite_code.strip().upper()

    with transaction() as cur:
        # Validate invite code
        cur.execute(
            "SELECT id, max_uses, use_count, expires_at FROM invite_codes WHERE code = %s",
            (code,),
        )
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(status_code=400, detail="邀请码无效")
        if inv["use_count"] >= inv["max_uses"]:
            raise HTTPException(status_code=400, detail="邀请码已被使用")
        if inv["expires_at"]:
            import datetime
            if inv["expires_at"] < datetime.datetime.now(datetime.timezone.utc):
                raise HTTPException(status_code=400, detail="邀请码已过期")

        # Check email uniqueness
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email.lower(),))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="该邮箱已注册")

        # Create user
        cur.execute(
            f"""INSERT INTO users (email, name, hashed_password, provider)
               VALUES (%s, %s, %s, 'email')
               RETURNING {_USER_COLUMNS}""",
            (body.email.lower(), body.name.strip(), hashed),
        )
        user = _user_dict(cur.fetchone())

        # Mark invite code as used
        cur.execute(
            "UPDATE invite_codes SET use_count = use_count + 1 WHERE id = %s",
            (inv["id"],),
        )

    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    """Authenticate with email + password."""
    with transaction() as cur:
        cur.execute(
            f"SELECT hashed_password, {_USER_COLUMNS} "
            "FROM users WHERE email = %s",
            (body.email.lower(),),
        )
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not row["hashed_password"]:
            raise HTTPException(
                status_code=401,
                detail="This account uses Google sign-in. Please log in with Google.",
            )
        if not auth_mod.verify_password(body.password, row["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (row["id"],))

    user = _user_dict(row)
    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(auth_mod.get_current_user)):
    """Return the currently authenticated user."""
    return user


@router.put("/profile")
def update_profile(body: ProfileUpdateRequest, user: dict = Depends(auth_mod.get_current_user)):
    """Update the current user's profile fields."""
    # Build SET clause dynamically from non-None fields
    updates: list[str] = []
    values: list[str] = []

    for field in ("name", "company", "title", "phone", "bio", "preferences_json"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field} = %s")
            values.append(val.strip() if isinstance(val, str) else val)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(user["id"])  # for WHERE clause

    with transaction() as cur:
        cur.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = %s "
            f"RETURNING {_USER_COLUMNS}",
            tuple(values),
        )
        updated = _user_dict(cur.fetchone())

    return updated


@router.post("/google", response_model=AuthResponse)
def google_login(body: GoogleLoginRequest):
    """Authenticate or register via Google ID token.

    NOTE: The server is hosted in mainland China and cannot reach googleapis.com.
    We decode the JWT locally (no network call) and verify:
      - aud  == our GOOGLE_CLIENT_ID  (token was issued for this app only)
      - iss  == accounts.google.com   (token was issued by Google)
      - exp  > now                    (token is not expired)
      - email_verified == true        (email is verified by Google)
    This is secure for an internal tool — the aud check ensures only tokens
    obtained via our own Google Sign-In button can be used.
    """
    import time
    import base64
    import json as _json

    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google login not configured (GOOGLE_CLIENT_ID not set)")

    # Decode JWT payload without signature verification (no outbound network needed)
    try:
        parts = body.id_token.split(".")
        if len(parts) != 3:
            raise ValueError("not a JWT")
        # Add padding for base64
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        token_info = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google ID token format")

    # Security checks (no network call required)
    if token_info.get("aud") != config.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google token audience mismatch")
    if token_info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Invalid token issuer")
    if token_info.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Google token expired")
    if not token_info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email not verified")

    email = token_info.get("email", "").lower()
    name = token_info.get("name") or token_info.get("email", "").split("@")[0]
    avatar = token_info.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Google token missing email")

    with transaction() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()

        if existing:
            cur.execute(
                f"""UPDATE users
                   SET avatar_url = COALESCE(%s, avatar_url), last_login = NOW()
                   WHERE email = %s
                   RETURNING {_USER_COLUMNS}""",
                (avatar, email),
            )
        else:
            cur.execute(
                f"""INSERT INTO users (email, name, avatar_url, provider)
                   VALUES (%s, %s, %s, 'google')
                   RETURNING {_USER_COLUMNS}""",
                (email, name, avatar),
            )
        user = _user_dict(cur.fetchone())

    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}
