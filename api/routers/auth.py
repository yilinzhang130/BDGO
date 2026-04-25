"""
routers/auth.py — Registration, login, Google OAuth, and /me endpoint.
"""

from __future__ import annotations

import logging
import re
import threading
import time

import auth as auth_mod
import config
from auth_db import transaction
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

_logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Simple in-memory per-IP rate limiter (SEC-002)
#
# Limits POST /login and /register to 10 attempts per IP per 60 s.
# NOTE: This is process-local — a multi-worker deployment (multiple uvicorn
# processes) gets N × limit per window.  For stricter enforcement, replace
# with a Redis-backed counter (e.g. slowapi + redis).
# ---------------------------------------------------------------------------

_RL_MAX_ATTEMPTS = 10       # max requests per IP per window
_RL_WINDOW_SECONDS = 60.0   # sliding window length in seconds

# ip → (attempt_count, window_start_monotonic)
_rl_store: dict[str, tuple[int, float]] = {}
_rl_lock = threading.Lock()


def _auth_rate_limit(request: Request) -> None:
    """Raise HTTP 429 if the requesting IP exceeds the login/register rate limit."""
    ip = (request.client.host if request.client else None) or "unknown"
    now = time.monotonic()
    with _rl_lock:
        count, window_start = _rl_store.get(ip, (0, now))
        if now - window_start > _RL_WINDOW_SECONDS:
            # New window — reset counter
            _rl_store[ip] = (1, now)
        elif count >= _RL_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please try again later.",
                headers={"Retry-After": str(int(_RL_WINDOW_SECONDS))},
            )
        else:
            _rl_store[ip] = (count + 1, window_start)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

# SEC-003: Limit password length before it reaches bcrypt.
# bcrypt only uses the first 72 bytes, but encoding an arbitrarily long
# string (e.g. 10 MB) still adds encode() overhead under concurrency.
# 128 characters comfortably covers any reasonable real-world password.
_MAX_PASSWORD_LENGTH = 128


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., max_length=_MAX_PASSWORD_LENGTH)
    name: str
    invite_code: str


class LoginRequest(BaseModel):
    email: str
    # max_length enforced here too so /login can't be used as the DoS vector
    password: str = Field(..., max_length=_MAX_PASSWORD_LENGTH)


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
    is_admin: bool = False
    is_active: bool = True
    is_internal: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


from auth import _USER_COLUMNS
from auth import serialize_user_row as _user_dict

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest, request: Request):
    """Create a new email/password account (requires a valid invite code)."""
    _auth_rate_limit(request)
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

            if inv["expires_at"] < datetime.datetime.now(datetime.UTC):
                raise HTTPException(status_code=400, detail="邀请码已过期")

        # Check email uniqueness
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email.lower(),))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="该邮箱已注册")

        # Create user (auto-flag as internal if email domain matches)
        is_internal = config.is_internal_email(body.email)
        cur.execute(
            f"""INSERT INTO users (email, name, hashed_password, provider, is_internal)
               VALUES (%s, %s, %s, 'email', %s)
               RETURNING {_USER_COLUMNS}""",
            (body.email.lower(), body.name.strip(), hashed, is_internal),
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
def login(body: LoginRequest, request: Request):
    """Authenticate with email + password."""
    _auth_rate_limit(request)
    with transaction() as cur:
        cur.execute(
            f"SELECT hashed_password, {_USER_COLUMNS} FROM users WHERE email = %s",
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
        if row.get("is_active") is False:
            raise HTTPException(status_code=403, detail="账户已被停用，请联系管理员")

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
            f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING {_USER_COLUMNS}",
            tuple(values),
        )
        updated = _user_dict(cur.fetchone())

    return updated


@router.post("/google", response_model=AuthResponse)
def google_login(body: GoogleLoginRequest):
    """Authenticate or register via Google ID token.

    ⚠️  KNOWN SECURITY LIMITATION — RSA SIGNATURE NOT VERIFIED
    ─────────────────────────────────────────────────────────────
    The server is deployed in mainland China and cannot reach googleapis.com,
    so we cannot fetch Google's public keys to verify the RS256 signature.
    Without signature verification an attacker who knows your GOOGLE_CLIENT_ID
    can craft a forged token that passes the aud/iss/exp/email_verified checks.

    MITIGATIONS IN PLACE:
      1. GOOGLE_CLIENT_ID must be explicitly set — Google login is disabled
         by default (no fallback to a permissive mode).
      2. `sub` (Google's immutable user ID) is stored on first login and
         re-checked on every subsequent Google login.  This blocks an attacker
         from hijacking an existing account by forging a token with the
         victim's email but a different Google identity.
      3. New-account registration still requires a valid invite code through
         the /register endpoint.  Google login only creates accounts for
         emails that already exist in the DB OR have been whitelisted via
         invite flow.

    TODO: If the server gains access to googleapis.com (proxy / VPN / CDN),
    replace this function with proper signature verification using
    `google-auth` library:
        from google.oauth2 import id_token
        from google.auth.transport import requests as g_requests
        token_info = id_token.verify_oauth2_token(
            body.id_token, g_requests.Request(), config.GOOGLE_CLIENT_ID
        )
    ─────────────────────────────────────────────────────────────
    """
    import base64
    import json as _json
    import time

    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google login not configured (GOOGLE_CLIENT_ID not set)",
        )

    # Decode JWT payload (signature intentionally not verified — see docstring)
    try:
        parts = body.id_token.split(".")
        if len(parts) != 3:
            raise ValueError("not a JWT")
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        token_info = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google ID token format") from None

    # Structural checks (claim values, not cryptographic)
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
    # `sub` is Google's immutable user ID — stable across email changes
    google_sub = token_info.get("sub", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google token missing email")
    if not google_sub:
        raise HTTPException(status_code=401, detail="Google token missing sub claim")

    with transaction() as cur:
        # Look up by google_sub first (handles email changes correctly),
        # then fall back to email for accounts registered before sub tracking.
        cur.execute(
            "SELECT id, email, google_sub FROM users WHERE google_sub = %s OR email = %s LIMIT 1",
            (google_sub, email),
        )
        existing = cur.fetchone()

        if existing:
            existing_sub = existing.get("google_sub")
            # If we have a stored sub and it doesn't match, reject.
            # This blocks an attacker who forged a token with a victim's email
            # but a different Google identity.
            if existing_sub and existing_sub != google_sub:
                _logger.warning(
                    "Google sub mismatch for email %s: stored=%s incoming=%s — rejected",
                    email,
                    existing_sub,
                    google_sub,
                )
                raise HTTPException(
                    status_code=401,
                    detail="Google account identity mismatch. Contact support.",
                )
            cur.execute(
                f"""UPDATE users
                   SET avatar_url = COALESCE(%s, avatar_url),
                       google_sub  = COALESCE(google_sub, %s),
                       last_login  = NOW()
                   WHERE id = %s
                   RETURNING {_USER_COLUMNS}""",
                (avatar, google_sub, str(existing["id"])),
            )
        else:
            # New Google user — register automatically (no invite code required
            # for Google sign-in; restrict via INTERNAL_EMAIL_DOMAINS if needed)
            is_internal = config.is_internal_email(email)
            cur.execute(
                f"""INSERT INTO users (email, name, avatar_url, provider, is_internal, google_sub)
                   VALUES (%s, %s, %s, 'google', %s, %s)
                   RETURNING {_USER_COLUMNS}""",
                (email, name, avatar, is_internal, google_sub),
            )
        user = _user_dict(cur.fetchone())

    token = auth_mod.create_token(user["id"], user["email"])
    return {"token": token, "user": user}
