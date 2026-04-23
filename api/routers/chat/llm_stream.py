"""Low-level LLM streaming: HTTP call, SSE decoding, cross-model fallback.

Separated from :mod:`streaming` so the chat handler orchestration stays
free of HTTP/parsing details. Callers get a uniform ``(event_type, payload)``
stream regardless of which concrete model ends up serving the request.
"""

from __future__ import annotations

import asyncio
import json
import logging

from llm_pool import PoolSaturatedError, acquire_for, get_client
from models import OVERLOAD_MSG, ModelSpec, fallback_chain

from .system_prompt import SYSTEM_PROMPT
from .tools import TOOLS

logger = logging.getLogger(__name__)


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

    body = {
        "model": model.api_model,
        "system": system_prompt or SYSTEM_PROMPT,
        "messages": messages,
        "max_tokens": 4096,
        "stream": True,
    }
    effective_tools = TOOLS if tools is None else tools
    if effective_tools:
        body["tools"] = effective_tools

    try:
        async with acquire_for(model) as (api_key, pool):
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
            }
            if model.anthropic_version:
                headers["anthropic-version"] = model.anthropic_version

            collected_content: list = []
            current_tool_use: dict | None = None
            current_text = ""
            stop_reason = None

            # Same key across 529 retries — 529 is provider-wide overload,
            # not a key-specific issue.
            max_retries = 3
            for attempt in range(max_retries):
                async with client.stream("POST", model.api_url, json=body, headers=headers) as resp:
                    if resp.status_code == 529:
                        await resp.aread()
                        if attempt < max_retries - 1:
                            wait = 2**attempt
                            logger.warning(
                                "MiniMax 529 (attempt %d/%d), retry in %ds",
                                attempt + 1,
                                max_retries,
                                wait,
                            )
                            await asyncio.sleep(wait)
                            continue
                        yield ("overloaded", model.id)
                        return
                    if resp.status_code != 200:
                        await resp.aread()
                        if resp.status_code in (408, 504):
                            msg = "请求超时，点击重试重新发送。"
                        elif resp.status_code in (401, 403):
                            msg = "AI服务认证失败，请联系管理员。"
                            if pool is not None:
                                pool.mute(api_key, seconds=300.0)
                        elif 500 <= resp.status_code < 600:
                            msg = "AI服务暂时不可用，请稍后重试。"
                            if pool is not None:
                                pool.mark_failure(api_key)
                        else:
                            msg = f"AI服务异常（{resp.status_code}），请稍后重试。"
                            if pool is not None:
                                pool.mark_failure(api_key)
                        yield ("error", msg)
                        return

                    # ── success: process the stream ──────────────────────────
                    buffer = ""
                    async for raw_chunk in resp.aiter_bytes():
                        buffer += raw_chunk.decode("utf-8", errors="replace")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            try:
                                data = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

                            et = data.get("type", "")

                            # ── Usage tracking (Anthropic-compat shape) ──
                            if et == "message_start":
                                u = (data.get("message", {}) or {}).get("usage") or {}
                                usage_accum["input_tokens"] += int(u.get("input_tokens") or 0)
                                usage_accum["output_tokens"] += int(u.get("output_tokens") or 0)
                            elif et == "message_delta":
                                u = data.get("usage") or {}
                                if "output_tokens" in u:
                                    usage_accum["_pending_output"] = int(u["output_tokens"] or 0)

                            if et == "content_block_start":
                                block = data.get("content_block", {})
                                if block.get("type") == "tool_use":
                                    current_tool_use = {
                                        "id": block.get("id"),
                                        "name": block.get("name"),
                                        "input_json": "",
                                    }
                                    yield ("tool_call_start", {"name": block.get("name")})
                                elif block.get("type") == "text":
                                    current_text = ""

                            elif et == "content_block_delta":
                                delta = data.get("delta", {})
                                dt = delta.get("type", "")
                                if dt == "text_delta":
                                    text = delta.get("text", "")
                                    current_text += text
                                    yield ("chunk", text)
                                elif dt == "input_json_delta" and current_tool_use is not None:
                                    current_tool_use["input_json"] += delta.get("partial_json", "")

                            elif et == "content_block_stop":
                                if current_tool_use is not None:
                                    try:
                                        inp = json.loads(current_tool_use["input_json"] or "{}")
                                    except json.JSONDecodeError:
                                        inp = {}
                                    collected_content.append(
                                        {
                                            "type": "tool_use",
                                            "id": current_tool_use["id"],
                                            "name": current_tool_use["name"],
                                            "input": inp,
                                        }
                                    )
                                    current_tool_use = None
                                elif current_text:
                                    collected_content.append({"type": "text", "text": current_text})
                                    current_text = ""

                            elif et == "message_delta":
                                stop_reason = data.get("delta", {}).get("stop_reason")

                            elif et == "message_stop":
                                pending = usage_accum.pop("_pending_output", 0)
                                if pending:
                                    usage_accum["output_tokens"] += pending
                                break

                if pool is not None:
                    pool.mark_success(api_key)

                yield ("_end", {"stop_reason": stop_reason, "content": collected_content})
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
