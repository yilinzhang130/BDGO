"""
credits.py — per-user credit balance + usage logging.

Design (minimum viable, Manus-inspired):

- Every user has a `credits` row with a `balance` (float, stored in micro-credits
  as BIGINT to avoid float drift in Postgres; balance API exposes whole credits).
  Actually we use NUMERIC here for readability; rounding is explicit.

- Each chat request:
    1. `ensure_balance(user_id)`   — check min threshold, raise 402 if empty
    2. Stream runs normally
    3. `record_usage(...)`          — insert usage_logs row + decrement credits

- Credit formula (relative units):
    credits_charged = input_tokens * input_weight + output_tokens * output_weight

- Initial grant: `DEFAULT_GRANT_CREDITS` on first ensure_balance lookup.
  New users get a welcome balance; top-ups are admin-only for now.

The schema migration runs via auth_db.py on startup (see _SCHEMA_SQL extension).
"""

from __future__ import annotations

import logging

import auth_db
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

# Welcome grant for new users, in whole credits
DEFAULT_GRANT_CREDITS = 10_000
# Require at least this many credits before starting a chat request
MIN_CREDITS_PER_REQUEST = 10


# ─────────────────────────────────────────────────────────────
# Schema (appended to auth_db._SCHEMA_SQL at import time)
# ─────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS credits (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_granted NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_spent NUMERIC(14, 2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(12),
    model_id VARCHAR(64) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    credits_charged NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_created
    ON usage_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_session
    ON usage_logs(session_id);
"""


# ─────────────────────────────────────────────────────────────
# Core operations
# ─────────────────────────────────────────────────────────────


def _ensure_row(cur, user_id: str) -> None:
    """Make sure a credits row exists for user_id; grant welcome credits on first touch."""
    cur.execute("SELECT 1 FROM credits WHERE user_id = %s", (user_id,))
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO credits (user_id, balance, total_granted)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, DEFAULT_GRANT_CREDITS, DEFAULT_GRANT_CREDITS),
        )


def get_balance(user_id: str) -> dict:
    """Return {balance, total_granted, total_spent} for a user."""
    with auth_db.transaction() as cur:
        _ensure_row(cur, user_id)
        cur.execute(
            """
            SELECT balance, total_granted, total_spent, updated_at
            FROM credits WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return {
        "balance": float(row["balance"]),
        "total_granted": float(row["total_granted"]),
        "total_spent": float(row["total_spent"]),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def ensure_balance(user_id: str, min_credits: float = MIN_CREDITS_PER_REQUEST) -> None:
    """Raise HTTPException(402) if balance < min_credits. Lazily grants welcome credits."""
    with auth_db.transaction() as cur:
        _ensure_row(cur, user_id)
        cur.execute("SELECT balance FROM credits WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        balance = float(row["balance"]) if row else 0.0
    if balance < min_credits:
        raise HTTPException(
            status_code=402,
            detail=f"Credit 余额不足（当前 {balance:.0f}，至少需要 {min_credits:.0f}）。请联系管理员充值。",
        )


def record_usage(
    user_id: str,
    session_id: str | None,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    input_weight: float,
    output_weight: float,
) -> float:
    """
    Insert a usage_logs row and decrement credits.balance atomically.
    Returns the credits_charged (as a positive float).
    Safe to call with zero tokens — will still write a 0-cost row for observability.
    """
    input_tokens = max(0, int(input_tokens or 0))
    output_tokens = max(0, int(output_tokens or 0))
    credits_charged = round(input_tokens * input_weight + output_tokens * output_weight, 2)

    try:
        with auth_db.transaction() as cur:
            _ensure_row(cur, user_id)
            cur.execute(
                """
                INSERT INTO usage_logs
                    (user_id, session_id, model_id, input_tokens, output_tokens, credits_charged)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, session_id, model_id, input_tokens, output_tokens, credits_charged),
            )
            cur.execute(
                """
                UPDATE credits
                   SET balance = GREATEST(balance - %s, 0),
                       total_spent = total_spent + %s,
                       updated_at = NOW()
                 WHERE user_id = %s
                """,
                (credits_charged, credits_charged, user_id),
            )
    except Exception:
        logger.exception(
            "Failed to record usage for user=%s session=%s model=%s",
            user_id,
            session_id,
            model_id,
        )
        # Don't surface billing errors to the user mid-chat
        return 0.0

    return credits_charged


def grant_credits(user_id: str, amount: float, reason: str = "") -> dict:
    """Admin top-up. Returns updated balance."""
    with auth_db.transaction() as cur:
        _ensure_row(cur, user_id)
        cur.execute(
            """
            UPDATE credits
               SET balance = balance + %s,
                   total_granted = total_granted + %s,
                   updated_at = NOW()
             WHERE user_id = %s
            RETURNING balance, total_granted, total_spent
            """,
            (amount, amount, user_id),
        )
        row = cur.fetchone()
    logger.info("Granted %s credits to user=%s (%s)", amount, user_id, reason)
    return {
        "balance": float(row["balance"]),
        "total_granted": float(row["total_granted"]),
        "total_spent": float(row["total_spent"]),
    }


def list_usage(user_id: str, limit: int = 50) -> list[dict]:
    """Recent usage rows for the current user."""
    with auth_db.transaction() as cur:
        cur.execute(
            """
            SELECT session_id, model_id, input_tokens, output_tokens,
                   credits_charged, created_at
              FROM usage_logs
             WHERE user_id = %s
             ORDER BY created_at DESC
             LIMIT %s
            """,
            (user_id, min(max(1, limit), 500)),
        )
        rows = cur.fetchall()
    return [
        {
            "session_id": r["session_id"],
            "model_id": r["model_id"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "credits_charged": float(r["credits_charged"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
