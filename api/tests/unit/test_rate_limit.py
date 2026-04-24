"""Unit tests for rate_limit.py — per-user RPM window + concurrent-slot
semaphore. Both rely on asyncio primitives + time.monotonic; tests
freeze the clock by patching rate_limit.time.monotonic so behaviour
stays deterministic."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture
def anyio_backend():
    # rate_limit.py is asyncio-native (asyncio.Lock / Semaphore), so pin
    # the anyio test backend to asyncio rather than trio.
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Each test starts with empty dicts — rate_limit keeps process-global
    state, which would leak across tests."""
    import rate_limit

    rate_limit._timestamps.clear()
    rate_limit._active.clear()
    yield
    rate_limit._timestamps.clear()
    rate_limit._active.clear()


class TestCheckRpm:
    """check_rpm enforces ``MAX_RPM`` requests per rolling 60 s per user."""

    @pytest.mark.anyio
    async def test_under_limit_accepts(self, monkeypatch):
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_RPM", 3)
        monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 0.0)

        # Three calls at t=0 should all pass (queue grows to 3).
        for _ in range(3):
            await rate_limit.check_rpm("user-A")
        assert len(rate_limit._timestamps["user-A"]) == 3

    @pytest.mark.anyio
    async def test_over_limit_raises_429(self, monkeypatch):
        import rate_limit
        from fastapi import HTTPException

        monkeypatch.setattr(rate_limit, "MAX_RPM", 2)
        monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 0.0)

        await rate_limit.check_rpm("user-A")
        await rate_limit.check_rpm("user-A")
        with pytest.raises(HTTPException) as exc_info:
            await rate_limit.check_rpm("user-A")
        assert exc_info.value.status_code == 429

    @pytest.mark.anyio
    async def test_window_evicts_old_timestamps(self, monkeypatch):
        """A request at t=0 and another at t=70 should leave the queue
        with only the new one (60s window evicts the first)."""
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_RPM", 2)
        fake_time = {"now": 0.0}
        monkeypatch.setattr(rate_limit.time, "monotonic", lambda: fake_time["now"])

        await rate_limit.check_rpm("user-A")
        fake_time["now"] = 70.0
        await rate_limit.check_rpm("user-A")
        # The 0.0 timestamp is outside the 60s window and must have been
        # evicted; only the 70.0 remains.
        assert list(rate_limit._timestamps["user-A"]) == [70.0]

    @pytest.mark.anyio
    async def test_empty_window_prunes_dict_entry(self, monkeypatch):
        """When the entire window empties, the dict entry is deleted —
        otherwise _timestamps grows unbounded over unique user ids."""
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_RPM", 5)
        fake_time = {"now": 0.0}
        monkeypatch.setattr(rate_limit.time, "monotonic", lambda: fake_time["now"])

        await rate_limit.check_rpm("user-A")
        assert "user-A" in rate_limit._timestamps

        fake_time["now"] = 120.0  # way past the 60s window
        await rate_limit.check_rpm("user-A")
        # The dict was briefly deleted by the prune branch, then rewritten
        # by the append (defaultdict recreates on access). Result should
        # be a single-entry deque at the new timestamp.
        assert list(rate_limit._timestamps["user-A"]) == [120.0]

    @pytest.mark.anyio
    async def test_per_user_isolation(self, monkeypatch):
        """One user's quota doesn't affect another's."""
        import rate_limit
        from fastapi import HTTPException

        monkeypatch.setattr(rate_limit, "MAX_RPM", 1)
        monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 0.0)

        await rate_limit.check_rpm("user-A")
        # user-A now blocked; user-B should still be fine.
        await rate_limit.check_rpm("user-B")
        with pytest.raises(HTTPException):
            await rate_limit.check_rpm("user-A")


class TestChatSlot:
    """chat_slot is an async context manager holding a concurrency slot."""

    @pytest.mark.anyio
    async def test_acquire_and_release(self, monkeypatch):
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_CONCURRENT_CHAT", 2)

        async with rate_limit.chat_slot("user-A"):
            assert rate_limit._active["user-A"] == 1
        # On exit, the dict entry is popped (remaining=0 branch).
        assert "user-A" not in rate_limit._active

    @pytest.mark.anyio
    async def test_refuses_when_saturated(self, monkeypatch):
        import rate_limit
        from fastapi import HTTPException

        monkeypatch.setattr(rate_limit, "MAX_CONCURRENT_CHAT", 2)

        async with rate_limit.chat_slot("user-A"), rate_limit.chat_slot("user-A"):
            # Two slots taken → a third must 429.
            with pytest.raises(HTTPException) as exc_info:
                async with rate_limit.chat_slot("user-A"):
                    pass
            assert exc_info.value.status_code == 429

    @pytest.mark.anyio
    async def test_slot_released_on_exception(self, monkeypatch):
        """If the wrapped code raises, the finally block must still
        decrement — otherwise an errored stream would leak its slot
        forever."""
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_CONCURRENT_CHAT", 1)

        with pytest.raises(RuntimeError):
            async with rate_limit.chat_slot("user-A"):
                raise RuntimeError("simulated stream error")

        # After the failure the user should have a free slot again.
        assert "user-A" not in rate_limit._active
        async with rate_limit.chat_slot("user-A"):
            pass

    @pytest.mark.anyio
    async def test_partial_release_keeps_remaining_count(self, monkeypatch):
        """With MAX=2 and one open slot, closing one must bring the
        count to 1 (not zero — that would evict and lose the other
        slot's bookkeeping)."""
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_CONCURRENT_CHAT", 2)

        outer_cm = rate_limit.chat_slot("user-A")
        await outer_cm.__aenter__()
        try:
            inner_cm = rate_limit.chat_slot("user-A")
            await inner_cm.__aenter__()
            await inner_cm.__aexit__(None, None, None)
            # Outer still running → count must be 1, not evicted.
            assert rate_limit._active["user-A"] == 1
        finally:
            await outer_cm.__aexit__(None, None, None)
        assert "user-A" not in rate_limit._active

    @pytest.mark.anyio
    async def test_parallel_users_do_not_share_quota(self, monkeypatch):
        """Two users each filling their own quota should not affect
        each other."""
        import rate_limit

        monkeypatch.setattr(rate_limit, "MAX_CONCURRENT_CHAT", 1)

        async def _holder(uid: str, hold_time: float):
            async with rate_limit.chat_slot(uid):
                await asyncio.sleep(hold_time)

        # Both can hold a slot simultaneously because they're different
        # user ids — the limit is per-user, not global.
        await asyncio.gather(_holder("user-A", 0.01), _holder("user-B", 0.01))
        assert "user-A" not in rate_limit._active
        assert "user-B" not in rate_limit._active
