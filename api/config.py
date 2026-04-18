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
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    _logger.warning("JWT_SECRET is not set — using insecure default (DO NOT use in production)")
    JWT_SECRET = "dev-secret-DO-NOT-USE-IN-PRODUCTION"
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
