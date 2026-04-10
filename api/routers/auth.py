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
import database

_logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_dict(row: dict) -> dict:
    """Normalise a DB row into a JSON-safe user dict."""
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("last_login"):
        d["last_login"] = d["last_login"].isoformat()
    d.pop("hashed_password", None)
    return d


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    """Create a new email/password account."""
    # Validate
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    hashed = auth_mod.hash_password(body.password)

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            # Check existing
            cur.execute("SELECT id FROM users WHERE email = %s", (body.email.lower(),))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email already registered")

            cur.execute(
                """INSERT INTO users (email, name, hashed_password, provider)
                   VALUES (%s, %s, %s, 'email')
                   RETURNING id, email, name, avatar_url, provider, created_at, last_login""",
                (body.email.lower(), body.name.strip(), hashed),
            )
            user = _user_dict(cur.fetchone())
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        _logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        conn.close()

    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    """Authenticate with email + password."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, avatar_url, hashed_password, provider, created_at, last_login "
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

        # Update last_login
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login = NOW() WHERE id = %s", (row["id"],)
            )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        _logger.exception("Login failed")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        conn.close()

    user = _user_dict(row)
    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(auth_mod.get_current_user)):
    """Return the currently authenticated user."""
    return user


@router.post("/google", response_model=AuthResponse)
def google_login(body: GoogleLoginRequest):
    """Authenticate or register via Google ID token."""
    # Verify token with Google
    try:
        resp = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": body.id_token},
            timeout=10.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Failed to verify Google token")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    token_info = resp.json()

    # Verify audience matches our client ID (if configured)
    if config.GOOGLE_CLIENT_ID and token_info.get("aud") != config.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google token audience mismatch")

    email = token_info.get("email", "").lower()
    name = token_info.get("name") or token_info.get("email", "").split("@")[0]
    avatar = token_info.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Google token missing email")

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            # Upsert: create if not exists, update avatar/last_login if exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """UPDATE users
                       SET avatar_url = COALESCE(%s, avatar_url),
                           last_login = NOW()
                       WHERE email = %s
                       RETURNING id, email, name, avatar_url, provider, created_at, last_login""",
                    (avatar, email),
                )
            else:
                cur.execute(
                    """INSERT INTO users (email, name, avatar_url, provider)
                       VALUES (%s, %s, %s, 'google')
                       RETURNING id, email, name, avatar_url, provider, created_at, last_login""",
                    (email, name, avatar),
                )

            user = _user_dict(cur.fetchone())
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        _logger.exception("Google login failed")
        raise HTTPException(status_code=500, detail="Google login failed")
    finally:
        conn.close()

    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}
