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
            '  python3 -c "import secrets; print(secrets.token_hex(32))"\n'
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

# MINIMAX_KEYS="key1,key2,..." for multi-plan deploys; falls back to single
# MINIMAX_API_KEY. MINIMAX_KEY is the first element — kept for back-compat
# with ModelSpec.api_key; real per-request routing happens in llm_pool.
_keys_raw = os.environ.get("MINIMAX_KEYS", "").strip()
if _keys_raw:
    MINIMAX_KEYS = [k.strip() for k in _keys_raw.split(",") if k.strip()]
else:
    _single = os.environ.get("MINIMAX_API_KEY", "").strip()
    MINIMAX_KEYS = [_single] if _single else []

MINIMAX_KEY = MINIMAX_KEYS[0] if MINIMAX_KEYS else ""
if not MINIMAX_KEYS:
    _logger.warning(
        "No MiniMax keys configured (set MINIMAX_KEYS or MINIMAX_API_KEY) — "
        "LLM-dependent endpoints will fail"
    )
elif len(MINIMAX_KEYS) > 1:
    _logger.info("MiniMax pool: %d keys configured", len(MINIMAX_KEYS))

# Set to the *minimum* plan limit across your keys — a mix of 2- and
# 3-concurrent plans must use 2, else the 2-plan rate-limits.
MINIMAX_PER_KEY_CONCURRENCY = int(os.environ.get("MINIMAX_PER_KEY_CONCURRENCY", "2"))

MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M1-80k")
MINIMAX_ANTHROPIC_VERSION = "2023-06-01"

# Auth header style for MiniMax requests. The standard pay-as-you-go API
# accepts Anthropic's "x-api-key" header; the MiniMax Token Plan / Coding
# Plan API requires "Authorization: Bearer <key>" instead. Keys issued on
# the Coding Plan use the "sk-cp-" prefix — we auto-detect those even if
# MINIMAX_AUTH_STYLE is left at the default, so users can paste the key
# without setting an extra flag.
#
# Override explicitly via env var ``MINIMAX_AUTH_STYLE=bearer`` if you have
# a non-prefixed Token-Plan key.
MINIMAX_AUTH_STYLE = os.environ.get("MINIMAX_AUTH_STYLE", "x-api-key").strip().lower()
if MINIMAX_AUTH_STYLE not in ("x-api-key", "bearer"):
    _logger.warning(
        "Unknown MINIMAX_AUTH_STYLE=%r; falling back to x-api-key. Valid: x-api-key | bearer",
        MINIMAX_AUTH_STYLE,
    )
    MINIMAX_AUTH_STYLE = "x-api-key"
# Auto-detect Coding-Plan keys regardless of explicit setting.
if MINIMAX_KEY.startswith("sk-cp-"):
    MINIMAX_AUTH_STYLE = "bearer"

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
BP_DIR = Path(
    os.environ.get(
        "BP_DIR",
        os.path.expanduser("~/.openclaw/workspace/BP"),
    )
)
CONFERENCES_DIR = Path(
    os.environ.get(
        "CONFERENCES_DIR",
        # Default: data/conferences/ next to this config file — ships with the
        # api/ image. Override via env var to point at a richer local workspace
        # directory.
        str(Path(__file__).parent / "data" / "conferences"),
    )
)
# Conference calendar YAML — source of truth for `/timing` outreach-window
# suggestions. Mirrors the conference-ingest MCP server's calendar so BDGO
# can read the same exact data without spawning the MCP runtime. Missing
# in production (servers without the openclaw workspace) → /timing falls
# back to its hardcoded annual-recurring event list.
CONFERENCE_CALENDAR_PATH = Path(
    os.environ.get(
        "CONFERENCE_CALENDAR_PATH",
        os.path.expanduser("~/.openclaw/skills/conference-ingest/conferences_calendar.yml"),
    )
)
REPORTS_DIR = Path(
    os.environ.get(
        "REPORTS_DIR",
        os.path.expanduser("~/.openclaw/workspace/Reports"),
    )
)

# ─────────────────────────────────────────────────────────────
# Logging / HTTP
# ─────────────────────────────────────────────────────────────

# Lower-cased once so callers can do `config.LOG_FORMAT == "json"`.
LOG_FORMAT = os.environ.get("LOG_FORMAT", "").lower()

# CORS allowlist; empty list = no cross-origin allowed (main.py adds its
# dev defaults when this is empty).
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

# ─────────────────────────────────────────────────────────────
# Rate limits (per-user)
# ─────────────────────────────────────────────────────────────

MAX_CONCURRENT_CHAT_PER_USER = int(os.environ.get("MAX_CONCURRENT_CHAT_PER_USER", "2"))
MAX_RPM_PER_USER = int(os.environ.get("MAX_RPM_PER_USER", "20"))

# ─────────────────────────────────────────────────────────────
# Third-party API keys (optional — features gated on presence)
# ─────────────────────────────────────────────────────────────

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

# Tavily accepts either a comma-separated multi-key form or a single key;
# services/external/search.py also falls back to reading ~/.openclaw/.env
# for local-dev convenience.
TAVILY_API_KEYS = os.environ.get("TAVILY_API_KEYS", "").strip()
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()

# SEC EDGAR requires a descriptive User-Agent on every call.
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "BD Go Research (bdgo@example.com)"

# ─────────────────────────────────────────────────────────────
# AIDD SSO (external auth bridge)
# ─────────────────────────────────────────────────────────────

AIDD_SSO_SECRET = os.environ.get("AIDD_SSO_SECRET", "")
AIDD_BASE_URL = os.environ.get("AIDD_BASE_URL", "https://aidd-two.vercel.app")

# ─────────────────────────────────────────────────────────────
# Credits (business thresholds — pricing experiments need env override,
# not a redeploy)
# ─────────────────────────────────────────────────────────────

DEFAULT_GRANT_CREDITS = int(os.environ.get("DEFAULT_GRANT_CREDITS", "10000"))
MIN_CREDITS_PER_REQUEST = int(os.environ.get("MIN_CREDITS_PER_REQUEST", "10"))

# ─────────────────────────────────────────────────────────────
# LLM / DB pool sizing (infra knobs)
# ─────────────────────────────────────────────────────────────

# Per-call timeout for the planner's LLM (plan generation + summarisation).
PLANNER_LLM_TIMEOUT_SECONDS = int(os.environ.get("PLANNER_LLM_TIMEOUT_SECONDS", "60"))

# Auth DB ThreadedConnectionPool sizing. Max is sized above default
# because chat endpoints offload DB calls to asyncio.to_thread workers
# (multiple concurrent threads per request).
AUTH_DB_POOL_MIN = int(os.environ.get("AUTH_DB_POOL_MIN", "2"))
AUTH_DB_POOL_MAX = int(os.environ.get("AUTH_DB_POOL_MAX", "20"))

# Max simultaneous async report tasks (buyer_profile, dd_checklist, …).
# Each task holds a thread + MiniMax key + potentially large in-memory objects
# (rNPV Excel ~10–50 MB). Default 6 keeps memory bounded for a single-worker
# deployment; raise via env var for multi-worker or high-memory hosts.
REPORT_MAX_WORKERS = int(os.environ.get("REPORT_MAX_WORKERS", "6"))


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
