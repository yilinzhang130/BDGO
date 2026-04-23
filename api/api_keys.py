"""
api_keys.py — Issue, verify, list, and revoke API keys for external callers.

Key format: ``bdgo_live_<32-char-base62>`` (42 chars total, ~190 bits entropy
in the body). Reserved env tag ``test_`` for a future sandbox.

Only ``sha256(full_key)`` is persisted. The raw key is returned *once* from
``create_key()`` and never retrievable again. ``revoked_at IS NULL`` is the
canonical "active" predicate — revoked rows are kept for audit.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import string
from datetime import UTC, datetime

import database
from fastapi import HTTPException

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Key format
# ─────────────────────────────────────────────────────────────

_VENDOR_PREFIX = "bdgo"
_DEFAULT_ENV = "live"
_BODY_ALPHABET = string.ascii_letters + string.digits  # base62
_BODY_LENGTH = 32
_PREFIX_DISPLAY_LENGTH = 14  # "bdgo_live_ab12"

# Public so tests / clients can build canonical keys without redefining the
# vendor string. Total key length = len(KEY_PREFIX) + _BODY_LENGTH = 42.
KEY_PREFIX = f"{_VENDOR_PREFIX}_{_DEFAULT_ENV}_"
KEY_LENGTH = len(KEY_PREFIX) + _BODY_LENGTH

# Header name expected by ``get_current_user`` for X-API-Key auth.
HEADER_NAME = "X-API-Key"

# Forgot-to-revoke ceiling per user; rotation never legitimately needs more.
MAX_ACTIVE_KEYS_PER_USER = 10


def _generate_key(env: str = _DEFAULT_ENV) -> str:
    """Return a fresh ``bdgo_<env>_<32-char-base62>`` token."""
    body = "".join(secrets.choice(_BODY_ALPHABET) for _ in range(_BODY_LENGTH))
    return f"{_VENDOR_PREFIX}_{env}_{body}"


def _hash_key(key: str) -> str:
    """SHA-256 hex digest. Deterministic so DB lookup can use a unique index.

    Plain SHA-256 (not bcrypt/argon2) is intentional: API keys here are 32-char
    base62 tokens (~190 bits of entropy) — brute-force over that space is
    infeasible even with GPU farms. A password-style KDF would force an O(N)
    scan of all stored hashes per auth attempt, which is unacceptable on the
    request hot path. This is the same pattern used by GitHub/Stripe/AWS for
    API token storage.
    """
    # codeql[py/weak-sensitive-data-hashing]: see docstring — high-entropy token, not a password.
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _serialize_row(row: dict) -> dict:
    """Normalise a Postgres row into a JSON-safe dict (drops key_hash)."""
    # Compute is_active from the raw datetime objects before stringifying —
    # round-tripping through fromisoformat would silently break if the column
    # is ever migrated to TIMESTAMPTZ (naive vs aware comparison TypeErrors).
    raw_expires = row.get("expires_at")
    is_active = row.get("revoked_at") is None and (
        raw_expires is None or raw_expires > _utc_now_naive()
    )

    d = dict(row)
    d["id"] = str(d["id"])
    d["user_id"] = str(d["user_id"])
    for ts in ("created_at", "last_used_at", "revoked_at", "expires_at"):
        if d.get(ts):
            d[ts] = d[ts].isoformat()
    d.pop("key_hash", None)
    d["is_active"] = is_active
    return d


def _utc_now_naive() -> datetime:
    # Postgres returns naive timestamps for TIMESTAMP-without-tz columns;
    # comparing against a tz-aware now() raises TypeError.
    return datetime.now(UTC).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────
# Core operations
# ─────────────────────────────────────────────────────────────


def create_key(
    user_id: str,
    name: str,
    scopes: list[str] | None = None,
    quota_daily: int | None = None,
    expires_at: datetime | None = None,
) -> dict:
    """Issue a new API key for ``user_id``.

    Returns ``{"key": "bdgo_live_...", "record": {...}}``. The full key is
    present **only** in the return value — subsequent reads go through
    ``list_keys`` which never surfaces it.
    """
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="API Key 名称不能为空")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="API Key 名称过长（最多 100 字符）")

    scopes = scopes or []
    if quota_daily is not None and quota_daily <= 0:
        raise HTTPException(status_code=400, detail="quota_daily 必须大于 0")

    with database.transaction() as cur:
        cur.execute(
            "SELECT COUNT(*)::int AS n FROM api_keys WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )
        active = cur.fetchone()["n"]
        if active >= MAX_ACTIVE_KEYS_PER_USER:
            raise HTTPException(
                status_code=400,
                detail=f"每个账户最多持有 {MAX_ACTIVE_KEYS_PER_USER} 个有效 API Key，请先吊销不用的 key",
            )

        # 190 bits of entropy + UNIQUE index on key_hash → collision is
        # statistically impossible. If the INSERT ever does conflict, a 500
        # is the right response (something is catastrophically wrong).
        full_key = _generate_key()
        key_hash = _hash_key(full_key)
        key_prefix = full_key[:_PREFIX_DISPLAY_LENGTH]
        cur.execute(
            """
            INSERT INTO api_keys
                (user_id, name, key_prefix, key_hash, scopes, quota_daily, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, user_id, name, key_prefix, scopes, quota_daily,
                      created_at, last_used_at, revoked_at, expires_at
            """,
            (user_id, name, key_prefix, key_hash, scopes, quota_daily, expires_at),
        )
        row = cur.fetchone()

    # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
    # Logs only the 8-char prefix (safe identifier), never the full token.
    _logger.info("issued token user=%s name=%s prefix=%s", user_id, name, key_prefix)
    return {"key": full_key, "record": _serialize_row(row)}


def verify_key(raw_key: str, *, client_ip: str | None = None) -> dict | None:
    """Look up an active key by hash.

    Returns ``{user_id, key_id, scopes, quota_daily}`` on success, or
    ``None`` if the key is unknown, revoked, or expired. Does *not* raise —
    the caller decides between 401 (unknown) and 403 (scope mismatch).

    Best-effort updates ``last_used_at`` (and ``last_used_ip`` when supplied)
    in the same UPDATE — failures are swallowed since stamping isn't worth
    failing the request over.
    """
    if not raw_key or not raw_key.startswith(f"{_VENDOR_PREFIX}_"):
        return None

    key_hash = _hash_key(raw_key)
    try:
        with database.transaction() as cur:
            cur.execute(
                """
                SELECT id, user_id, scopes, quota_daily, expires_at
                  FROM api_keys
                 WHERE key_hash = %s
                   AND revoked_at IS NULL
                """,
                (key_hash,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            if row["expires_at"] is not None and row["expires_at"] < _utc_now_naive():
                return None
            cur.execute(
                """
                UPDATE api_keys
                   SET last_used_at = NOW(),
                       last_used_ip = COALESCE(%s, last_used_ip)
                 WHERE id = %s
                """,
                (client_ip[:45] if client_ip else None, row["id"]),
            )
        return {
            "key_id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "scopes": list(row["scopes"] or []),
            "quota_daily": row["quota_daily"],
        }
    except Exception:
        _logger.exception("verify_key failed")
        return None


def list_keys(user_id: str, include_revoked: bool = False) -> list[dict]:
    """Return all keys for ``user_id`` sorted newest-first. Never includes the hash."""
    sql = """
        SELECT id, user_id, name, key_prefix, scopes, quota_daily,
               created_at, last_used_at, last_used_ip, revoked_at, expires_at
          FROM api_keys
         WHERE user_id = %s
    """
    if not include_revoked:
        sql += " AND revoked_at IS NULL"
    sql += " ORDER BY created_at DESC"

    with database.transaction() as cur:
        cur.execute(sql, (user_id,))
        rows = cur.fetchall()
    return [_serialize_row(r) for r in rows]


def revoke_key(user_id: str, key_id: str) -> dict:
    """Mark a key as revoked. Returns the updated row, or 404 if not found.

    Scoped to ``user_id`` so User A can't revoke User B's keys — even if
    they guess the UUID.
    """
    with database.transaction() as cur:
        cur.execute(
            """
            UPDATE api_keys
               SET revoked_at = NOW()
             WHERE id = %s
               AND user_id = %s
               AND revoked_at IS NULL
            RETURNING id, user_id, name, key_prefix, scopes, quota_daily,
                      created_at, last_used_at, revoked_at, expires_at
            """,
            (key_id, user_id),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="API Key 未找到或已吊销")
    # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
    # Logs only the DB row UUID, never the token itself.
    _logger.info("revoked token user=%s row_id=%s", user_id, key_id)
    return _serialize_row(row)
