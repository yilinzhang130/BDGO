"""
api_request_log.py — Per-key API call ledger (write + read).

Writes are synchronous today (one DB round trip per API-key request).
Upgrade path when p95 hurts: process-local queue + background flusher.
"""

from __future__ import annotations

import logging

import database

_logger = logging.getLogger(__name__)


def log_request(
    *,
    key_id: str,
    user_id: str,
    method: str,
    path: str,
    status: int,
    latency_ms: int | None = None,
) -> None:
    """Insert one api_request_logs row. Never raises.

    ``path`` is the URL path component only — query strings would leak
    secrets to anyone with DB read access; the middleware passes
    ``request.url.path`` which already excludes them.
    """
    try:
        with database.transaction() as cur:
            cur.execute(
                """
                INSERT INTO api_request_logs
                    (key_id, user_id, method, path, status, latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (key_id, user_id, method[:10], path[:255], int(status), latency_ms),
            )
    except Exception:
        # codeql[py/clear-text-logging-sensitive-data]: key_id is a DB row UUID, not the API token.
        _logger.exception("Failed to write api_request_log row_id=%s path=%s", key_id, path)


def count_today(key_id: str) -> int:
    """Number of requests this key has made since 00:00 UTC today.

    Returns 0 on DB errors — fail-open so a logging outage doesn't lock
    users out of their own API. This is the same tradeoff ``log_request``
    makes: availability over strict accounting.
    """
    try:
        with database.transaction() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS n
                  FROM api_request_logs
                 WHERE key_id = %s
                   AND created_at >= (NOW() AT TIME ZONE 'UTC')::date
                """,
                (key_id,),
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0
    except Exception:
        _logger.exception("Failed to count today's requests for key=%s", key_id)
        return 0


def recent_for_user(user_id: str, limit: int = 100) -> list[dict]:
    """Last N requests made by a user (across all their keys).

    Powers the developer-portal usage tab. Returns newest first.
    """
    limit = min(max(1, int(limit)), 500)
    try:
        with database.transaction() as cur:
            cur.execute(
                """
                SELECT l.method, l.path, l.status, l.latency_ms, l.created_at,
                       k.name AS key_name, k.key_prefix
                  FROM api_request_logs l
                  JOIN api_keys k ON k.id = l.key_id
                 WHERE l.user_id = %s
                 ORDER BY l.created_at DESC
                 LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
    except Exception:
        _logger.exception("Failed to load recent requests for user=%s", user_id)
        return []

    return [
        {
            "method": r["method"],
            "path": r["path"],
            "status": r["status"],
            "latency_ms": r["latency_ms"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "key_name": r["key_name"],
            "key_prefix": r["key_prefix"],
        }
        for r in rows
    ]
