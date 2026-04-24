"""Unit tests for llm_pool.py — per-key scheduling + circuit breaker
for the MiniMax Anthropic-compat API pool. The LLMPool class itself
is the main unit; the module-level init/teardown is exercised
indirectly (integration-tested by real API calls).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.fixture
def anyio_backend():
    # acquire() uses asyncio.Semaphore / Lock — pin to asyncio backend.
    return "asyncio"


class TestConstructor:
    def test_empty_keys_rejected(self):
        from llm_pool import LLMPool

        with pytest.raises(ValueError):
            LLMPool("minimax", [], per_key_concurrency=2)

    def test_zero_concurrency_rejected(self):
        from llm_pool import LLMPool

        with pytest.raises(ValueError):
            LLMPool("minimax", ["k1"], per_key_concurrency=0)

    def test_total_capacity_is_product(self):
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1", "k2", "k3"], per_key_concurrency=2)
        assert p.total_capacity == 6


class TestAcquire:
    @pytest.mark.anyio
    async def test_yields_one_of_the_keys(self):
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1", "k2"], per_key_concurrency=1)
        async with p.acquire() as key:
            assert key in ("k1", "k2")

    @pytest.mark.anyio
    async def test_in_flight_decrements_on_exit(self):
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=2)
        async with p.acquire() as _:
            assert sum(s.in_flight for s in p.slots) == 1
        assert sum(s.in_flight for s in p.slots) == 0

    @pytest.mark.anyio
    async def test_picks_least_loaded_key(self):
        """With k1 already at 1 in-flight and k2 idle, a new acquire
        should pick k2."""
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1", "k2"], per_key_concurrency=2)
        # Hold k1 by directly bumping its counter (simulating an
        # already-active request on that key).
        p.slots[0].in_flight = 1
        async with p.acquire() as key:
            assert key == "k2"

    @pytest.mark.anyio
    async def test_skips_muted_keys(self):
        """If one key is muted, acquire should prefer the unmuted one."""
        import time

        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1", "k2"], per_key_concurrency=2)
        p.slots[0].muted_until = time.monotonic() + 30  # mute k1
        async with p.acquire() as key:
            assert key == "k2"

    @pytest.mark.anyio
    async def test_all_muted_falls_back_to_full_pool(self):
        """If every key is muted, we still have to pick one — better to
        retry than to block the user. Pool falls back to full set."""
        import time

        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1", "k2"], per_key_concurrency=2)
        now_plus_30 = time.monotonic() + 30
        p.slots[0].muted_until = now_plus_30
        p.slots[1].muted_until = now_plus_30
        async with p.acquire() as key:
            assert key in ("k1", "k2")

    @pytest.mark.anyio
    async def test_saturation_times_out(self):
        """When the global semaphore is fully held and acquire times out,
        PoolSaturatedError is raised (not asyncio.TimeoutError — callers
        shouldn't need to know about the underlying primitive)."""
        from llm_pool import LLMPool, PoolSaturatedError

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)

        async def _hold():
            async with p.acquire():
                await asyncio.sleep(0.5)

        hold_task = asyncio.create_task(_hold())
        await asyncio.sleep(0.05)  # let _hold take the slot
        with pytest.raises(PoolSaturatedError):
            async with p.acquire(timeout=0.05):
                pass
        await hold_task


class TestMarkFailure:
    def test_single_failure_does_not_mute(self):
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)
        p.mark_failure("k1")
        assert p.slots[0].fail_count == 1
        assert p.slots[0].muted_until == 0.0

    def test_three_failures_mutes_key(self):
        """FAIL_STREAK_THRESHOLD = 3: third consecutive failure trips
        the soft circuit breaker."""
        import time

        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)
        for _ in range(3):
            p.mark_failure("k1", mute_seconds=10.0)
        assert p.slots[0].fail_count == 3
        assert p.slots[0].muted_until > time.monotonic()

    def test_unknown_key_is_silently_ignored(self):
        """This is a hot path — raising on an unknown key during
        failure handling would mask the real error."""
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)
        p.mark_failure("not-a-real-key")  # must not raise
        assert p.slots[0].fail_count == 0


class TestMute:
    def test_force_mute_regardless_of_streak(self):
        """mute() is for hard errors (401/403) — should mute immediately,
        not wait for the streak threshold."""
        import time

        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)
        p.mute("k1", seconds=5.0)
        assert p.slots[0].muted_until > time.monotonic()
        # Also bumps fail_count to threshold so mark_success has to be
        # called to reset.
        assert p.slots[0].fail_count >= 3


class TestMarkSuccess:
    def test_resets_fail_streak(self):
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)
        p.mark_failure("k1")
        p.mark_failure("k1")
        p.mark_success("k1")
        assert p.slots[0].fail_count == 0
        assert p.slots[0].muted_until == 0.0

    def test_success_on_clean_key_is_noop(self):
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["k1"], per_key_concurrency=1)
        p.mark_success("k1")  # no failures to clear
        assert p.slots[0].fail_count == 0


class TestSnapshot:
    def test_shape_matches_ops_endpoint_expectation(self):
        """snapshot() backs /api/admin/llm-pool. The keys here are
        part of an HTTP contract, so changes need deliberate attention."""
        from llm_pool import LLMPool

        p = LLMPool("minimax", ["key-aaa", "key-bbb"], per_key_concurrency=2)
        snap = p.snapshot()

        assert snap["provider"] == "minimax"
        assert snap["total_capacity"] == 4
        assert len(snap["keys"]) == 2
        entry = snap["keys"][0]
        assert set(entry) == {
            "suffix",
            "in_flight",
            "max_concurrent",
            "muted",
            "mute_remaining_s",
            "total_requests",
            "total_failures",
            "fail_streak",
        }
        # Suffix is safe-to-log short form, not the full key.
        assert entry["suffix"] == "ey-aaa"


class TestKeySuffix:
    def test_short_key_returns_placeholder(self):
        """Internal helper — keys shorter than n chars return '?' so
        logs don't leak the whole short key."""
        from llm_pool import _key_suffix

        assert _key_suffix("abc") == "?"

    def test_empty_key_returns_placeholder(self):
        from llm_pool import _key_suffix

        assert _key_suffix("") == "?"

    def test_normal_key_returns_tail(self):
        from llm_pool import _key_suffix

        assert _key_suffix("sk-1234567890abcdef") == "abcdef"


class TestAcquireFor:
    @pytest.mark.anyio
    async def test_non_minimax_uses_static_key(self):
        """Non-MiniMax providers (Claude/DeepSeek) don't go through the
        pool — they yield their static model.api_key and a pool of None."""
        from llm_pool import acquire_for

        model = SimpleNamespace(provider="deepseek", api_key="sk-deepseek-123")
        async with acquire_for(model) as (key, pool):
            assert key == "sk-deepseek-123"
            assert pool is None

    @pytest.mark.anyio
    async def test_minimax_without_pool_falls_through_to_static_key(self, monkeypatch):
        """When the pool isn't initialized, MiniMax requests should still
        work using the model's static api_key — otherwise every test
        would need to spin up the pool."""
        import llm_pool

        monkeypatch.setattr(llm_pool, "_pool", None)
        monkeypatch.setattr(llm_pool, "_http_client", None)

        model = SimpleNamespace(provider="minimax", api_key="sk-mm-static")
        async with llm_pool.acquire_for(model) as (key, pool):
            assert key == "sk-mm-static"
            assert pool is None


class TestGetPool:
    def test_raises_if_not_initialized(self, monkeypatch):
        """get_pool() must fail loudly — a None pool would silently
        fall through to a confusing AttributeError on first use."""
        import llm_pool

        monkeypatch.setattr(llm_pool, "_pool", None)
        with pytest.raises(RuntimeError, match="LLM pool not initialized"):
            llm_pool.get_pool()

    def test_get_client_raises_if_not_initialized(self, monkeypatch):
        import llm_pool

        monkeypatch.setattr(llm_pool, "_http_client", None)
        with pytest.raises(RuntimeError):
            llm_pool.get_client()

    def test_pool_available_checks_both_pool_and_client(self, monkeypatch):
        import llm_pool

        monkeypatch.setattr(llm_pool, "_pool", object())
        monkeypatch.setattr(llm_pool, "_http_client", None)
        assert llm_pool.pool_available() is False

        monkeypatch.setattr(llm_pool, "_http_client", object())
        assert llm_pool.pool_available() is True
