"""
llm_pool.py — Multi-key API pool for LLM providers.

Problem: one MiniMax "coding plan" allows only 2-3 concurrent streams. To
serve N concurrent users we run M plans in parallel and round-robin across
their keys. Each key has its own in-flight counter so we never exceed the
plan's concurrency and get rate-limited.

Design:
  - Single shared httpx.AsyncClient (connection pool reuse)
  - Global semaphore = total capacity gate; waiters wake when any slot frees
  - Under pick_lock: choose the least-loaded unmuted key
  - Soft circuit breaker: 3 consecutive failures → key muted for 60s
  - Hard mute: mute(key, seconds) for 401/403-type permanent errors

Currently scopes to MiniMax only. Adding a second provider pool is
straightforward — instantiate another LLMPool and register it.

Multi-worker note: this is in-process. If you later switch to gunicorn
with multiple workers, each worker has its own view of pool load → keys
can be oversubscribed. At that point, swap to Redis-backed counters.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

FAIL_STREAK_THRESHOLD = 3
DEFAULT_MUTE_SECONDS = 60.0
DEFAULT_ACQUIRE_TIMEOUT = 120.0


@dataclass
class KeySlot:
    key: str
    in_flight: int = 0
    fail_count: int = 0
    muted_until: float = 0.0  # monotonic ts; 0 = active
    total_requests: int = 0
    total_failures: int = 0


class LLMPool:
    """Pool of API keys for a single provider."""

    def __init__(self, provider: str, keys: list[str], per_key_concurrency: int):
        if not keys:
            raise ValueError(f"LLMPool({provider}): at least one key required")
        if per_key_concurrency < 1:
            raise ValueError("per_key_concurrency must be >= 1")
        self.provider = provider
        self.per_key_concurrency = per_key_concurrency
        self.slots: list[KeySlot] = [KeySlot(key=k) for k in keys]
        self._by_key: dict[str, KeySlot] = {s.key: s for s in self.slots}
        # Global gate = total capacity. A waiter is released as soon as
        # any slot frees up, then we pick the least-loaded one.
        self._global_sem = asyncio.Semaphore(len(keys) * per_key_concurrency)
        self._pick_lock = asyncio.Lock()

    @property
    def total_capacity(self) -> int:
        return len(self.slots) * self.per_key_concurrency

    @asynccontextmanager
    async def acquire(
        self,
        timeout: float = DEFAULT_ACQUIRE_TIMEOUT,
    ) -> AsyncIterator[str]:
        """Yield an API key, blocking up to `timeout` seconds if saturated.

        The slot is held for the full lifetime of the context. Callers must
        keep the context short (one LLM request), not the whole user turn.
        """
        try:
            await asyncio.wait_for(self._global_sem.acquire(), timeout=timeout)
        except TimeoutError as e:
            raise PoolSaturatedError(
                f"{self.provider} pool saturated for {timeout}s (capacity={self.total_capacity})"
            ) from e

        chosen: KeySlot | None = None
        try:
            now = time.monotonic()
            async with self._pick_lock:
                active = [s for s in self.slots if s.muted_until <= now]
                pool = active if active else self.slots
                chosen = min(pool, key=lambda s: (s.in_flight, s.fail_count))
                chosen.in_flight += 1
                chosen.total_requests += 1
            yield chosen.key
        finally:
            # Decrement before releasing the global sem so a waker sees
            # the updated in_flight when it picks the next slot. Plain
            # integer op is safe on a single-threaded event loop.
            if chosen is not None:
                chosen.in_flight = max(0, chosen.in_flight - 1)
            self._global_sem.release()

    def mark_failure(
        self,
        key: str,
        mute_seconds: float = DEFAULT_MUTE_SECONDS,
    ) -> None:
        """Record a failure. After FAIL_STREAK_THRESHOLD in a row, temporarily mute the key."""
        slot = self._by_key.get(key)
        if slot is None:
            return
        slot.fail_count += 1
        slot.total_failures += 1
        if slot.fail_count >= FAIL_STREAK_THRESHOLD:
            slot.muted_until = time.monotonic() + mute_seconds
            logger.warning(
                "%s key …%s muted for %.0fs after %d failures",
                self.provider,
                _key_suffix(key),
                mute_seconds,
                slot.fail_count,
            )

    def mute(self, key: str, seconds: float = DEFAULT_MUTE_SECONDS) -> None:
        """Force-mute a key immediately — for hard errors (401/403) where
        there's no point letting other requests hit the same wall."""
        slot = self._by_key.get(key)
        if slot is None:
            return
        slot.fail_count = max(slot.fail_count, FAIL_STREAK_THRESHOLD)
        slot.total_failures += 1
        slot.muted_until = time.monotonic() + seconds
        logger.warning(
            "%s key …%s force-muted for %.0fs",
            self.provider,
            _key_suffix(key),
            seconds,
        )

    def mark_success(self, key: str) -> None:
        """Reset failure streak after a successful call."""
        slot = self._by_key.get(key)
        if slot is None:
            return
        if slot.fail_count:
            logger.info(
                "%s key …%s recovered after %d failures",
                self.provider,
                _key_suffix(key),
                slot.fail_count,
            )
        slot.fail_count = 0
        slot.muted_until = 0.0

    def snapshot(self) -> dict:
        """Pool state for ops/admin endpoint."""
        now = time.monotonic()
        return {
            "provider": self.provider,
            "total_capacity": self.total_capacity,
            "keys": [
                {
                    "suffix": _key_suffix(s.key),
                    "in_flight": s.in_flight,
                    "max_concurrent": self.per_key_concurrency,
                    "muted": s.muted_until > now,
                    "mute_remaining_s": max(0.0, s.muted_until - now),
                    "total_requests": s.total_requests,
                    "total_failures": s.total_failures,
                    "fail_streak": s.fail_count,
                }
                for s in self.slots
            ],
        }


class PoolSaturatedError(RuntimeError):
    """Raised when acquire() times out — all keys busy for too long."""


def _key_suffix(key: str, n: int = 6) -> str:
    """Last n chars of the key, for safe logging."""
    return key[-n:] if key and len(key) >= n else "?"


_pool: LLMPool | None = None
_http_client: httpx.AsyncClient | None = None


def init_pool() -> None:
    """Build the MiniMax pool and shared httpx client. Call once at startup."""
    global _pool, _http_client

    # Imported lazily so config.py parsing errors surface at startup, not at
    # module import time of this file (which may happen before env is ready).
    from config import MINIMAX_KEYS, MINIMAX_PER_KEY_CONCURRENCY

    if not MINIMAX_KEYS:
        logger.warning(
            "No MiniMax keys configured; LLM endpoints will fail until "
            "MINIMAX_KEYS or MINIMAX_API_KEY is set."
        )
        return

    _pool = LLMPool(
        provider="minimax",
        keys=MINIMAX_KEYS,
        per_key_concurrency=MINIMAX_PER_KEY_CONCURRENCY,
    )

    # Size the httpx connection pool to match LLM capacity. Each LLM call
    # holds one streaming connection; double for slack (uploads, health).
    cap = _pool.total_capacity
    limits = httpx.Limits(
        max_connections=max(20, cap * 2),
        max_keepalive_connections=max(10, cap),
        keepalive_expiry=60.0,
    )
    _http_client = httpx.AsyncClient(timeout=300, limits=limits)

    logger.info(
        "LLM pool: provider=minimax keys=%d per_key=%d total_capacity=%d",
        len(MINIMAX_KEYS),
        MINIMAX_PER_KEY_CONCURRENCY,
        cap,
    )


async def close_pool() -> None:
    """Close the shared httpx client. Call on FastAPI shutdown."""
    global _http_client, _pool
    if _http_client is not None:
        try:
            await _http_client.aclose()
        finally:
            _http_client = None
    _pool = None


def get_pool() -> LLMPool:
    """Return the MiniMax pool. Raises if init_pool() hasn't run."""
    if _pool is None:
        raise RuntimeError(
            "LLM pool not initialized — init_pool() must run on startup "
            "(check FastAPI lifespan in main.py)"
        )
    return _pool


def get_client() -> httpx.AsyncClient:
    """Return the shared httpx client. Raises if init_pool() hasn't run."""
    if _http_client is None:
        raise RuntimeError("Shared httpx client not initialized — init_pool() must run on startup")
    return _http_client


def pool_available() -> bool:
    """True if init_pool() succeeded with at least one key."""
    return _pool is not None and _http_client is not None


@asynccontextmanager
async def acquire_for(model) -> AsyncIterator[tuple[str, LLMPool | None]]:
    """Yield (api_key, pool_or_None) for the given model.

    MiniMax goes through the shared pool (fair multi-key scheduling).
    Other providers use the static ``ModelSpec.api_key``.
    """
    if model.provider == "minimax" and pool_available():
        pool = get_pool()
        async with pool.acquire() as key:
            yield key, pool
    else:
        yield model.api_key, None
