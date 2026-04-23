"""
Tavily web search helper with sequential key drain.

Why sequential (not round-robin): using multiple keys from the same IP
simultaneously triggers Tavily's fraud detection and gets keys banned.
The rule is: drain one key until exhausted/banned, then advance to the next.
See feedback_tavily_key_rotation.md for history.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT = 10.0


def _load_keys() -> list[str]:
    """Load Tavily keys from env. Tries TAVILY_API_KEYS (comma-separated) first,
    then TAVILY_API_KEY (single), then reads ~/.openclaw/.env as fallback."""
    # Env vars
    multi = os.environ.get("TAVILY_API_KEYS", "").strip()
    if multi:
        return [k.strip() for k in multi.split(",") if k.strip()]

    single = os.environ.get("TAVILY_API_KEY", "").strip()
    if single:
        return [single]

    # Fallback: read ~/.openclaw/.env directly since the API server doesn't
    # necessarily inherit the openclaw shell's env
    env_file = Path.home() / ".openclaw" / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("TAVILY_API_KEYS="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return [k.strip() for k in value.split(",") if k.strip()]
                if line.startswith("TAVILY_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return [value] if value else []
        except Exception as e:
            logger.warning("Failed to read Tavily keys from .env: %s", e)
    return []


# Module-level key state. "banned" means don't retry this key in this process;
# "usage" tracks how many successful calls made with each key (for stable sort).
# All reads/writes are guarded by _lock for thread safety (services run in daemon threads).
_KEYS: list[str] = _load_keys()
_banned: set[str] = set()
_usage: dict[str, int] = {k: 0 for k in _KEYS}
_lock = threading.Lock()


def _active_keys() -> list[str]:
    """Most-used first (sequential drain), skipping banned keys."""
    with _lock:
        alive = [k for k in _KEYS if k not in _banned]
        alive.sort(key=lambda k: _usage.get(k, 0), reverse=True)
    return alive


def search_web(
    query: str,
    max_results: int = 3,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Search Tavily, return list of {title, url, snippet}.

    Gracefully degrades to [] on any failure (no keys, all banned, network error).
    Callers should always handle the empty case.
    """
    if not query.strip():
        return []

    keys = _active_keys()
    if not keys:
        if not _KEYS:
            logger.warning("No Tavily keys configured — returning empty results")
        else:
            logger.warning("All %d Tavily keys are banned for this process", len(_KEYS))
        return []

    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }

    with httpx.Client(timeout=timeout) as client:
        for key in keys:
            try:
                resp = client.post(
                    TAVILY_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                )
            except httpx.HTTPError as e:
                logger.warning("Tavily request network error: %s", e)
                continue  # Try next key on network errors

            if resp.status_code == 200:
                with _lock:
                    _usage[key] = _usage.get(key, 0) + 1
                try:
                    data = resp.json()
                except Exception:
                    return []
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": (r.get("content") or r.get("raw_content") or "")[:500],
                    }
                    for r in data.get("results", [])
                ]

            if resp.status_code in (401, 403, 429):
                # Ban this key for the rest of the process and try the next one
                logger.warning(
                    "Tavily key banned (status=%d, key=...%s) — advancing",
                    resp.status_code,
                    key[-6:],
                )
                with _lock:
                    _banned.add(key)
                continue

            # Some other server error — don't ban, just give up this attempt
            logger.warning("Tavily HTTP %d: %s", resp.status_code, resp.text[:200])
            return []

    return []
