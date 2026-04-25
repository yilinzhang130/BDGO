"""Low-level LLM streaming: HTTP call, SSE decoding, cross-model fallback.

Separated from :mod:`streaming` so the chat handler orchestration stays
free of HTTP/parsing details. Callers get a uniform ``(event_type, payload)``
stream regardless of which concrete model ends up serving the request.

``call_minimax_stream`` is the hot path. Its branches were split into
small helpers so the top-level generator reads as: build request →
acquire key → retry on 529 → parse SSE stream. Each helper is
independently unit-testable (see tests/unit/routers/chat/test_llm_stream.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

from llm_pool import PoolSaturatedError, acquire_for, get_client
from models import OVERLOAD_MSG, ModelSpec, fallback_chain

from .system_prompt import SYSTEM_PROMPT
from .tools import TOOLS

logger = logging.getLogger(__name__)

_MAX_529_RETRIES = 3


def _build_request(
    messages: list,
    model: ModelSpec,
    system_prompt: str | None,
    tools: list | None,
) -> tuple[dict, dict]:
    """Return ``(body, static_headers)`` for a streaming chat call.

    ``x-api-key`` is added later per-attempt because it depends on the
    key the pool hands out.
    """
    body: dict[str, Any] = {
        "model": model.api_model,
        "system": [
            {
                "type": "text",
                "text": system_prompt or SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": messages,
        "max_tokens": 4096,
        "stream": True,
    }
    effective_tools = TOOLS if tools is None else tools
    if effective_tools:
        # Mark the last tool with cache_control so the whole tools block is
        # eligible for prompt caching. Shallow-copy to avoid mutating TOOLS.
        body["tools"] = [
            *effective_tools[:-1],
            {**effective_tools[-1], "cache_control": {"type": "ephemeral"}},
        ]

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if model.anthropic_version:
        headers["anthropic-version"] = model.anthropic_version
    return body, headers


async def _error_message_for_status(resp, pool, api_key: str) -> str:
    """Drain the error body, update pool health, return the user-facing message.

    The side effects (``pool.mute`` for auth errors, ``pool.mark_failure``
    for 5xx) are kept here because they must happen in lock-step with
    deciding the message — a 401 that updates the pool but not the
    user message, or vice versa, would leave the pool inconsistent.
    """
    await resp.aread()
    status = resp.status_code
    if status in (408, 504):
        return "请求超时，点击重试重新发送。"
    if status in (401, 403):
        if pool is not None:
            pool.mute(api_key, seconds=300.0)
        return "AI服务认证失败，请联系管理员。"
    if 500 <= status < 600:
        if pool is not None:
            pool.mark_failure(api_key)
        return "AI服务暂时不可用，请稍后重试。"
    if pool is not None:
        pool.mark_failure(api_key)
    return f"AI服务异常（{status}），请稍后重试。"


def _accumulate_usage(data: dict, usage_accum: dict) -> None:
    """Update ``usage_accum`` in place from a message_start / message_delta event.

    MiniMax (Anthropic-compat) reports input + output tokens in
    message_start, then running output token totals in message_delta.
    The final message_stop is the signal to commit the running
    output-token count (see ``_consume_content_event``).
    """
    et = data.get("type", "")
    if et == "message_start":
        u = (data.get("message", {}) or {}).get("usage") or {}
        usage_accum["input_tokens"] += int(u.get("input_tokens") or 0)
        usage_accum["output_tokens"] += int(u.get("output_tokens") or 0)
        usage_accum["cache_read_input_tokens"] = usage_accum.get(
            "cache_read_input_tokens", 0
        ) + int(u.get("cache_read_input_tokens") or 0)
    elif et == "message_delta":
        u = data.get("usage") or {}
        if "output_tokens" in u:
            usage_accum["_pending_output"] = int(u["output_tokens"] or 0)


class _StreamState:
    """Mutable state for one SSE stream. Kept as a dataclass-like object
    so helpers can mutate without passing many locals around."""

    __slots__ = (
        "collected_content",
        "current_tool_use",
        "current_text",
        "stop_reason",
        "finished",
    )

    def __init__(self) -> None:
        self.collected_content: list[dict] = []
        self.current_tool_use: dict | None = None
        self.current_text: str = ""
        self.stop_reason: str | None = None
        self.finished: bool = False


def _on_block_start(state: _StreamState, data: dict):
    """Handle ``content_block_start``. Yields at most one event."""
    block = data.get("content_block", {})
    if block.get("type") == "tool_use":
        state.current_tool_use = {
            "id": block.get("id"),
            "name": block.get("name"),
            "input_json": "",
        }
        yield ("tool_call_start", {"name": block.get("name")})
    elif block.get("type") == "text":
        state.current_text = ""


def _on_block_delta(state: _StreamState, data: dict):
    """Handle ``content_block_delta``. Yields at most one ``chunk`` event."""
    delta = data.get("delta", {})
    dt = delta.get("type", "")
    if dt == "text_delta":
        text = delta.get("text", "")
        state.current_text += text
        yield ("chunk", text)
    elif dt == "input_json_delta" and state.current_tool_use is not None:
        state.current_tool_use["input_json"] += delta.get("partial_json", "")


def _on_block_stop(state: _StreamState) -> None:
    """Close out the current content block, appending it to collected_content."""
    if state.current_tool_use is not None:
        try:
            inp = json.loads(state.current_tool_use["input_json"] or "{}")
        except json.JSONDecodeError:
            inp = {}
        state.collected_content.append(
            {
                "type": "tool_use",
                "id": state.current_tool_use["id"],
                "name": state.current_tool_use["name"],
                "input": inp,
            }
        )
        state.current_tool_use = None
    elif state.current_text:
        state.collected_content.append({"type": "text", "text": state.current_text})
        state.current_text = ""


def _consume_content_event(state: _StreamState, data: dict, usage_accum: dict):
    """Route one content-oriented event to the right state transition.

    Yields ``(event_type, payload)`` tuples (zero or more per event).
    Mutates ``state`` and ``usage_accum`` in place.
    """
    _accumulate_usage(data, usage_accum)
    et = data.get("type", "")

    if et == "content_block_start":
        yield from _on_block_start(state, data)
    elif et == "content_block_delta":
        yield from _on_block_delta(state, data)
    elif et == "content_block_stop":
        _on_block_stop(state)
    elif et == "message_delta":
        state.stop_reason = data.get("delta", {}).get("stop_reason")
    elif et == "message_stop":
        pending = usage_accum.pop("_pending_output", 0)
        if pending:
            usage_accum["output_tokens"] += pending
        state.finished = True


async def _iter_sse_events(resp):
    """Yield parsed JSON dicts from an Anthropic-compat SSE response."""
    buffer = ""
    async for raw_chunk in resp.aiter_bytes():
        buffer += raw_chunk.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line.startswith("data: "):
                continue
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                continue


async def call_minimax_stream(
    messages: list,
    model: ModelSpec,
    usage_accum: dict,
    system_prompt: str | None = None,
    tools: list | None = None,
):
    """Single call to the selected LLM; yields (event_type, payload) pairs.

    ``usage_accum`` is updated in place with input/output token counts
    reported via message_start / message_delta events.

    ``system_prompt`` overrides :data:`SYSTEM_PROMPT` — used to inject
    plan constraints when executing an approved plan.

    ``tools`` overrides :data:`TOOLS`. Pass ``[]`` to disable tool use
    entirely (quick-search mode).
    """
    client = get_client()
    body, static_headers = _build_request(messages, model, system_prompt, tools)

    try:
        async with acquire_for(model) as (api_key, pool):
            headers = {**static_headers, "x-api-key": api_key}

            for attempt in range(_MAX_529_RETRIES):
                state = _StreamState()
                async with client.stream("POST", model.api_url, json=body, headers=headers) as resp:
                    if resp.status_code == 529:
                        await resp.aread()
                        if attempt < _MAX_529_RETRIES - 1:
                            wait = (2**attempt) * (0.5 + random.random())
                            logger.warning(
                                "MiniMax 529 (attempt %d/%d), retry in %.1fs",
                                attempt + 1,
                                _MAX_529_RETRIES,
                                wait,
                            )
                            await asyncio.sleep(wait)
                            continue
                        yield ("overloaded", model.id)
                        return
                    if resp.status_code != 200:
                        msg = await _error_message_for_status(resp, pool, api_key)
                        yield ("error", msg)
                        return

                    async for event in _iter_sse_events(resp):
                        for tup in _consume_content_event(state, event, usage_accum):
                            yield tup
                        if state.finished:
                            break

                if pool is not None:
                    pool.mark_success(api_key)
                yield (
                    "_end",
                    {"stop_reason": state.stop_reason, "content": state.collected_content},
                )
                return
    except PoolSaturatedError as e:
        logger.warning("MiniMax pool saturated: %s", e)
        yield ("error", "AI服务繁忙，请稍后再试。")


async def stream_with_fallback(
    messages: list,
    model: ModelSpec,
    usage_accum: dict,
    system_prompt: str | None = None,
    tools: list | None = None,
):
    """Wrap :func:`call_minimax_stream` with cross-provider fallback on overload.

    If the primary model signals ``overloaded`` (529 exhausted), tries each
    model in :func:`fallback_chain` before giving up with an ``error`` event.
    """
    models_to_try = [model] + fallback_chain(model.id)
    for try_model in models_to_try:
        async for event_type, payload in call_minimax_stream(
            messages, try_model, usage_accum, system_prompt, tools
        ):
            if event_type == "overloaded":
                logger.warning("Model %s overloaded, trying fallback", try_model.id)
                break
            yield event_type, payload
        else:
            return  # inner loop finished without break → success
    yield ("error", OVERLOAD_MSG)
