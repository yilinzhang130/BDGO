"""Unit tests for the helpers extracted from ``call_minimax_stream``
in M-008. The generator itself (the full request → retry → parse
loop) is exercised by integration tests with real MiniMax traffic;
here we cover the pure helpers that are now independently testable.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class TestBuildRequest:
    """_build_request assembles the request body + static headers —
    the last thing an LLM call does before hitting the wire."""

    def test_default_system_and_tools(self):
        from routers.chat.llm_stream import _build_request
        from routers.chat.system_prompt import SYSTEM_PROMPT
        from routers.chat.tools import TOOLS

        model = SimpleNamespace(api_model="abab7-chat", anthropic_version="2023-06-01")
        body, headers = _build_request([{"role": "user", "content": "hi"}], model, None, None)

        assert body["model"] == "abab7-chat"
        assert body["system"] == SYSTEM_PROMPT
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert body["stream"] is True
        # None means "use defaults", which includes the TOOLS registry.
        assert body["tools"] == TOOLS
        assert headers["anthropic-version"] == "2023-06-01"
        # x-api-key is intentionally NOT added here — that's per-attempt.
        assert "x-api-key" not in headers

    def test_system_prompt_override_wins(self):
        """Plan execution injects its own system prompt; the default
        must NOT be preferred."""
        from routers.chat.llm_stream import _build_request

        model = SimpleNamespace(api_model="m", anthropic_version=None)
        body, _ = _build_request([], model, "custom system", None)
        assert body["system"] == "custom system"

    def test_empty_tools_disables_tools_entirely(self):
        """Quick-search mode passes ``tools=[]`` to disable tool use;
        body must NOT contain a ``tools`` key (sending [] would still
        let the model think tools are available)."""
        from routers.chat.llm_stream import _build_request

        model = SimpleNamespace(api_model="m", anthropic_version=None)
        body, _ = _build_request([], model, None, [])
        assert "tools" not in body

    def test_missing_anthropic_version_omits_header(self):
        """Non-Anthropic-compat models (if ever added) shouldn't get
        the header at all."""
        from routers.chat.llm_stream import _build_request

        model = SimpleNamespace(api_model="m", anthropic_version=None)
        _, headers = _build_request([], model, None, None)
        assert "anthropic-version" not in headers


class TestErrorMessageForStatus:
    """_error_message_for_status maps HTTP status → user-facing Chinese
    string + side-effect on the pool. Side effects and the message
    must stay in lock-step (see the function's docstring)."""

    class FakeResp:
        def __init__(self, status: int):
            self.status_code = status

        async def aread(self):
            return b""

    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.mark.anyio
    async def test_408_is_timeout_message_no_pool_change(self):
        from routers.chat.llm_stream import _error_message_for_status

        pool = SimpleNamespace(
            mute=lambda *a, **k: pytest.fail("408 must not touch pool"),
            mark_failure=lambda *a, **k: pytest.fail("408 must not touch pool"),
        )
        msg = await _error_message_for_status(self.FakeResp(408), pool, "k1")
        assert "超时" in msg

    @pytest.mark.anyio
    async def test_504_also_timeout(self):
        from routers.chat.llm_stream import _error_message_for_status

        msg = await _error_message_for_status(self.FakeResp(504), None, "k1")
        assert "超时" in msg

    @pytest.mark.anyio
    async def test_401_force_mutes_key(self):
        """401 means the key is bad — mute for 5 min so no other
        concurrent request hits the same wall."""
        from routers.chat.llm_stream import _error_message_for_status

        calls: list = []
        pool = SimpleNamespace(
            mute=lambda key, seconds: calls.append(("mute", key, seconds)),
            mark_failure=lambda *a, **k: pytest.fail("401 uses mute, not mark_failure"),
        )
        msg = await _error_message_for_status(self.FakeResp(401), pool, "k1")
        assert "认证" in msg
        assert calls == [("mute", "k1", 300.0)]

    @pytest.mark.anyio
    async def test_403_also_force_mutes(self):
        from routers.chat.llm_stream import _error_message_for_status

        calls: list = []
        pool = SimpleNamespace(
            mute=lambda key, seconds: calls.append(("mute", key, seconds)),
            mark_failure=lambda *a, **k: pytest.fail("no mark_failure for 403"),
        )
        await _error_message_for_status(self.FakeResp(403), pool, "k1")
        assert calls == [("mute", "k1", 300.0)]

    @pytest.mark.anyio
    async def test_500_increments_failure_streak(self):
        """5xx is a transient wobble — mark_failure (soft) not mute,
        so one request failure doesn't evict the key for 5 min."""
        from routers.chat.llm_stream import _error_message_for_status

        calls: list = []
        pool = SimpleNamespace(
            mute=lambda *a, **k: pytest.fail("5xx uses mark_failure, not mute"),
            mark_failure=lambda key: calls.append(("mark_failure", key)),
        )
        msg = await _error_message_for_status(self.FakeResp(502), pool, "k1")
        assert "暂时不可用" in msg
        assert calls == [("mark_failure", "k1")]

    @pytest.mark.anyio
    async def test_unknown_4xx_falls_through_to_generic(self):
        from routers.chat.llm_stream import _error_message_for_status

        calls: list = []
        pool = SimpleNamespace(mute=lambda *a, **k: None, mark_failure=lambda k: calls.append(k))
        msg = await _error_message_for_status(self.FakeResp(418), pool, "k1")
        # 418 isn't specially handled; still mark_failure so repeat
        # weirdness trips the circuit breaker.
        assert "异常" in msg
        assert "418" in msg
        assert calls == ["k1"]

    @pytest.mark.anyio
    async def test_no_pool_does_not_crash(self):
        """Non-MiniMax providers have pool=None — the function must
        still produce a message without pool side-effects."""
        from routers.chat.llm_stream import _error_message_for_status

        msg = await _error_message_for_status(self.FakeResp(500), None, "k1")
        assert "暂时不可用" in msg


class TestAccumulateUsage:
    def test_message_start_adds_input_and_output(self):
        from routers.chat.llm_stream import _accumulate_usage

        acc = {"input_tokens": 0, "output_tokens": 0}
        _accumulate_usage(
            {
                "type": "message_start",
                "message": {"usage": {"input_tokens": 100, "output_tokens": 5}},
            },
            acc,
        )
        assert acc["input_tokens"] == 100
        assert acc["output_tokens"] == 5

    def test_message_delta_sets_pending_only(self):
        """Running output-token count shouldn't commit until message_stop
        (otherwise we'd double-count on any retry)."""
        from routers.chat.llm_stream import _accumulate_usage

        acc = {"input_tokens": 0, "output_tokens": 0}
        _accumulate_usage({"type": "message_delta", "usage": {"output_tokens": 42}}, acc)
        assert acc["output_tokens"] == 0
        assert acc["_pending_output"] == 42

    def test_other_events_are_noops(self):
        from routers.chat.llm_stream import _accumulate_usage

        acc = {"input_tokens": 0, "output_tokens": 0}
        _accumulate_usage({"type": "content_block_delta"}, acc)
        assert acc == {"input_tokens": 0, "output_tokens": 0}


class TestConsumeContentEvent:
    """_consume_content_event is the central state-machine driver —
    each test covers one transition."""

    def test_text_delta_yields_chunk_and_accumulates_text(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        events = list(
            _consume_content_event(
                state,
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hi"}},
                {"input_tokens": 0, "output_tokens": 0},
            )
        )
        assert events == [("chunk", "hi")]
        assert state.current_text == "hi"

    def test_tool_use_start_yields_tool_call_start(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        events = list(
            _consume_content_event(
                state,
                {
                    "type": "content_block_start",
                    "content_block": {"type": "tool_use", "id": "t1", "name": "search"},
                },
                {"input_tokens": 0, "output_tokens": 0},
            )
        )
        assert events == [("tool_call_start", {"name": "search"})]
        assert state.current_tool_use is not None
        assert state.current_tool_use["id"] == "t1"

    def test_tool_use_input_delta_accumulates_json(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        list(
            _consume_content_event(
                state,
                {
                    "type": "content_block_start",
                    "content_block": {"type": "tool_use", "id": "t1", "name": "s"},
                },
                {},
            )
        )
        list(
            _consume_content_event(
                state,
                {
                    "type": "content_block_delta",
                    "delta": {"type": "input_json_delta", "partial_json": '{"q":'},
                },
                {},
            )
        )
        list(
            _consume_content_event(
                state,
                {
                    "type": "content_block_delta",
                    "delta": {"type": "input_json_delta", "partial_json": '"foo"}'},
                },
                {},
            )
        )
        assert state.current_tool_use["input_json"] == '{"q":"foo"}'

    def test_block_stop_on_tool_parses_input_json(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        state.current_tool_use = {"id": "t1", "name": "search", "input_json": '{"q": "foo"}'}
        list(_consume_content_event(state, {"type": "content_block_stop"}, {}))
        assert state.collected_content == [
            {"type": "tool_use", "id": "t1", "name": "search", "input": {"q": "foo"}}
        ]
        assert state.current_tool_use is None

    def test_block_stop_on_bad_tool_json_still_appends(self):
        """Malformed JSON from the model shouldn't drop the tool_use
        entry — fall back to empty dict so downstream routing still
        picks up the call."""
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        state.current_tool_use = {"id": "t1", "name": "s", "input_json": "{broken"}
        list(_consume_content_event(state, {"type": "content_block_stop"}, {}))
        assert state.collected_content == [
            {"type": "tool_use", "id": "t1", "name": "s", "input": {}}
        ]

    def test_block_stop_on_text_appends_accumulated(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        state.current_text = "hello"
        list(_consume_content_event(state, {"type": "content_block_stop"}, {}))
        assert state.collected_content == [{"type": "text", "text": "hello"}]
        assert state.current_text == ""

    def test_message_stop_commits_pending_output(self):
        """The _pending_output buffered from message_delta events must
        only commit at message_stop — otherwise retries would double-
        count tokens already billed."""
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        usage = {"input_tokens": 0, "output_tokens": 0, "_pending_output": 50}
        list(_consume_content_event(state, {"type": "message_stop"}, usage))
        assert usage["output_tokens"] == 50
        assert "_pending_output" not in usage
        assert state.finished is True

    def test_message_stop_without_pending_is_clean(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        usage = {"input_tokens": 0, "output_tokens": 10}
        list(_consume_content_event(state, {"type": "message_stop"}, usage))
        assert usage["output_tokens"] == 10
        assert state.finished is True

    def test_message_delta_captures_stop_reason(self):
        from routers.chat.llm_stream import _consume_content_event, _StreamState

        state = _StreamState()
        list(
            _consume_content_event(
                state,
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
                {"input_tokens": 0, "output_tokens": 0},
            )
        )
        assert state.stop_reason == "end_turn"
