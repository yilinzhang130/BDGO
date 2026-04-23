"""
rate_limit.py — Per-user rate limiting for the chat endpoint.

Two guards, both in-memory and process-local (good enough for a single-
process uvicorn deployment; for multi-process / multi-pod setups upgrade
to Redis-backed counters):

  check_rpm(user_id)  — sliding-window MAX_RPM req/min; checked once on
                        entry, raises 429 immediately if exceeded.

  chat_slot(user_id)  — concurrent-request semaphore (MAX_CONCURRENT_CHAT
                        parallel streams per user); holds a slot for the
                        entire SSE stream lifetime so one user can't
                        monopolise the MiniMax pool.

Both limits are env-tunable (MAX_CONCURRENT_CHAT_PER_USER, MAX_RPM_PER_USER)
so capacity planning stays in ops land rather than requiring code changes
when you buy more MiniMax plans.

Admins bypass both limits (is_admin flag checked by the caller).
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from config import MAX_CONCURRENT_CHAT_PER_USER, MAX_RPM_PER_USER
from fastapi import HTTPException

# Sized against the MiniMax pool: with 10 keys × 2 concurrency = 20 total
# slots, per-user 2 streams serves ~10 active users without queueing.
MAX_CONCURRENT_CHAT = MAX_CONCURRENT_CHAT_PER_USER
MAX_RPM = MAX_RPM_PER_USER

# Concurrent slot tracking
_active: dict[str, int] = defaultdict(int)
_active_lock = asyncio.Lock()

# Sliding-window timestamp queues (per user, monotonic seconds)
_timestamps: dict[str, deque] = defaultdict(deque)
_ts_lock = asyncio.Lock()


async def check_rpm(user_id: str) -> None:
    """Raise HTTP 429 if the user has sent ≥ MAX_RPM messages in the last 60 s."""
    now = time.monotonic()
    async with _ts_lock:
        q = _timestamps[user_id]
        # Evict timestamps outside the 60-second window.
        while q and now - q[0] > 60.0:
            q.popleft()
        if not q:
            # Window is empty — prune dict entry to prevent unbounded growth,
            # then fall through to append (defaultdict recreates on access).
            del _timestamps[user_id]
        elif len(q) >= MAX_RPM:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，每分钟最多 {MAX_RPM} 次对话，请稍候片刻再试。",
            )
        _timestamps[user_id].append(now)


@asynccontextmanager
async def chat_slot(user_id: str):
    """Async context manager that holds one concurrent-stream slot.

    Usage::

        async def _guarded(gen):
            async with chat_slot(user_id):
                async for chunk in gen:
                    yield chunk

    Raises HTTP 429 immediately if the user already has MAX_CONCURRENT_CHAT
    streams in flight. The slot is released when the wrapped generator
    finishes (including error / client disconnect paths).
    """
    async with _active_lock:
        if _active[user_id] >= MAX_CONCURRENT_CHAT:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"您当前已有 {MAX_CONCURRENT_CHAT} 个对话正在进行中，"
                    "请等待其中一个完成后再发起新对话。"
                ),
            )
        _active[user_id] += 1
    try:
        yield
    finally:
        async with _active_lock:
            remaining = max(0, _active[user_id] - 1)
            if remaining == 0:
                # Evict zero-count entries so the dict doesn't grow once per
                # unique user_id ever seen.
                _active.pop(user_id, None)
            else:
                _active[user_id] = remaining
