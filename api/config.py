"""
Shared configuration constants.

Keep secrets/endpoints/paths in one place so rotation is a single-file change.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import HTTPException

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Auth / database
# ─────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── JWT_SECRET ────────────────────────────────────────────────
# Production (DATABASE_URL set): JWT_SECRET MUST be provided — hard fail
# otherwise a deployment typo would silently expose all accounts.
# Dev (no DATABASE_URL): generate a random per-session secret so the app
# is still usable, but all sessions die on restart (expected in dev).
_jwt_secret_env = os.environ.get("JWT_SECRET", "").strip()
if not _jwt_secret_env:
    if DATABASE_URL:
        raise RuntimeError(
            "\n\n*** FATAL: JWT_SECRET is not set but DATABASE_URL is configured. ***\n"
            "Running in production without a JWT secret would allow anyone to forge\n"
            "authentication tokens and take over any account.\n\n"
            "Generate a secret and add it to your .env:\n"
            "  python3 -c \"import secrets; print(secrets.token_hex(32))\"\n"
        )
    import secrets as _secrets
    _jwt_secret_env = _secrets.token_hex(32)
    _logger.warning(
        "JWT_SECRET not set — generated a random secret for this dev session. "
        "All tokens will be invalidated on restart. "
        "Set JWT_SECRET in your .env to persist sessions."
    )
elif len(_jwt_secret_env) < 32:
    _logger.warning(
        "JWT_SECRET is shorter than 32 characters (%d). "
        "Use at least 32 random bytes for production security.",
        len(_jwt_secret_env),
    )
JWT_SECRET: str = _jwt_secret_env

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

# Email domains that are auto-flagged as "internal" at registration.
# Internal users see subjective/BD-operations fields; external users don't.
# Admin can override this flag per-user from the admin dashboard.
INTERNAL_EMAIL_DOMAINS = {
    d.strip().lower()
    for d in os.environ.get("INTERNAL_EMAIL_DOMAINS", "yafocapital.com").split(",")
    if d.strip()
}


def is_internal_email(email: str) -> bool:
    """Return True if the email's domain matches INTERNAL_EMAIL_DOMAINS."""
    if not email or "@" not in email:
        return False
    return email.rsplit("@", 1)[1].strip().lower() in INTERNAL_EMAIL_DOMAINS

# ─────────────────────────────────────────────────────────────
# LLM endpoints
# ─────────────────────────────────────────────────────────────

MINIMAX_URL = os.environ.get(
    "MINIMAX_URL",
    "https://api.minimaxi.com/anthropic/v1/messages",
)
MINIMAX_KEY = os.environ.get("MINIMAX_API_KEY", "")
if not MINIMAX_KEY:
    _logger.warning("MINIMAX_API_KEY is not set — LLM-dependent endpoints will fail")
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M1-80k")
MINIMAX_ANTHROPIC_VERSION = "2023-06-01"

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

CRM_DB_PATH = os.environ.get(
    "CRM_DB_PATH",
    os.path.expanduser("~/.openclaw/workspace/crm-database/crm.db"),
)
CRM_BACKEND = os.environ.get("CRM_BACKEND", "sqlite").lower()
CRM_PG_DSN = os.environ.get("CRM_PG_DSN", "dbname=bdgo")
GUIDELINES_DB_PATH = os.environ.get(
    "GUIDELINES_DB_PATH",
    os.path.expanduser("~/.openclaw/workspace/guidelines/guidelines.db"),
)
BP_DIR = Path(os.environ.get(
    "BP_DIR",
    os.path.expanduser("~/.openclaw/workspace/BP"),
))
CONFERENCES_DIR = Path(os.environ.get(
    "CONFERENCES_DIR",
    # Default: conferences/ folder next to this config file (gets rsynced with api/)
    # Override via env var to point at a richer local workspace directory
    str(Path(__file__).parent / "conferences"),
))
REPORTS_DIR = Path(os.environ.get(
    "REPORTS_DIR",
    os.path.expanduser("~/.openclaw/workspace/Reports"),
))


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

def safe_path_within(base: Path, filename: str) -> Path:
    """Resolve filename strictly inside base dir, rejecting path traversal.

    Raises HTTPException(400) on any attempt to escape base.
    """
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    resolved = (base / safe_name).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return resolved
