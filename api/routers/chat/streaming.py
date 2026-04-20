"""Chat stream orchestration — tool-use loop and plan-only phase.

Delegates the low-level pieces to sibling modules:
    * :mod:`llm_stream`       — HTTP + SSE decoding + fallback chain
    * :mod:`tool_loop`        — per-tool execution / circuit breaker / entity emit
    * :mod:`attachments_prep` — file extraction and user-message build
    * :mod:`billing`          — credits accounting
    * :mod:`sse`              — SSE frame helpers
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

import planner as planner_mod
from models import resolve_model

from .attachments_prep import prepare_message_with_attachments
from .billing import charge_turn
from .chat_store import (
    ensure_session,
    load_history,
    save_entities,
    save_message,
)
from .compaction import compact_if_needed
from .llm_stream import stream_with_fallback
from .sse import sse, sse_done
from .system_prompt import SYSTEM_PROMPT
from .tool_loop import execute_tool_call

logger = logging.getLogger(__name__)

# Strong refs for fire-and-forget background tasks. asyncio only holds weak
# refs to tasks, so without this they can be GC'd mid-flight.
_bg_tasks: set[asyncio.Task] = set()

# Upper bound on how many tool rounds one user turn can fan out into.
# After this many rounds we force a text-only synthesis call so the user
# always gets a reply.
MAX_TOOL_ROUNDS = 8


async def _strip_trailing_empty_assistant(history: list) -> None:
    """When executing a confirmed plan, drop trailing empty assistant turns.

    The user message + empty plan-card placeholder are already in history
    from the planner phase. We strip the empty assistant so the LLM sees
    the user prompt as the latest turn.
    """
    while history and history[-1].get("role") == "assistant":
        c = history[-1].get("content")
        empty = (
            not c
            or (isinstance(c, str) and not c.strip())
            or (
                isinstance(c, list)
                and not any(
                    isinstance(b, dict) and b.get("text", "").strip()
                    for b in c
                )
            )
        )
        if empty:
            history.pop()
        else:
            break


async def stream_chat(req):
    """Main tool-use loop with streaming. Yields SSE-formatted strings."""
    session_id = req.session_id
    user_id = req.user_id
    # Field visibility: admins + internal employees see everything;
    # external users get HIDDEN_FIELDS stripped from tool results.
    can_see_internal = bool(req.is_admin or req.is_internal)

    model = resolve_model(req.model_id)

    # If the client confirmed a plan, inject its constraints into the
    # system prompt so the LLM sticks to the approved steps.
    active_system_prompt: str | None = None
    if req.plan_confirm and req.plan_confirm.selected_steps:
        active_system_prompt = SYSTEM_PROMPT + planner_mod.build_plan_constraint(
            req.plan_confirm.plan_title,
            [s.model_dump() for s in req.plan_confirm.selected_steps],
        )

    usage_accum = {"input_tokens": 0, "output_tokens": 0}

    if user_id:
        await asyncio.to_thread(ensure_session, session_id, user_id)

    history = await asyncio.to_thread(load_history, session_id)

    is_executing_plan = req.plan_confirm is not None
    if is_executing_plan:
        await _strip_trailing_empty_assistant(history)

    user_text, attachments_json = await prepare_message_with_attachments(
        req.message, req.file_ids
    )

    if not is_executing_plan:
        history.append({"role": "user", "content": user_text})
        await asyncio.to_thread(
            save_message, session_id, "user", user_text,
            attachments_json=attachments_json,
        )

    # Auto-compact: strip old tool blocks; summarize if still over budget.
    history = await compact_if_needed(session_id, history, model)

    all_entities: list[dict] = []
    # Per-request tool error counter: tool_name → consecutive failure count.
    # If any tool fails twice in a row, we inject a stop hint so the LLM
    # doesn't burn all rounds retrying the same broken tool.
    tool_error_counts: dict[str, int] = {}

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            for _iteration in range(MAX_TOOL_ROUNDS):
                final_content = None
                final_stop_reason = None

                async for event_type, payload in stream_with_fallback(
                    client, history, model, usage_accum,
                    system_prompt=active_system_prompt,
                ):
                    if event_type == "chunk":
                        yield sse("chunk", content=payload)
                    elif event_type == "tool_call_start":
                        yield sse("tool_call", name=payload["name"])
                    elif event_type == "error":
                        yield sse("error", message=payload)
                        yield sse_done()
                        return
                    elif event_type == "_end":
                        final_content = payload["content"]
                        final_stop_reason = payload["stop_reason"]

                if final_content is None:
                    break

                history.append({"role": "assistant", "content": final_content})

                tool_uses = [b for b in final_content if b.get("type") == "tool_use"]
                if final_stop_reason == "tool_use" and tool_uses:
                    tool_results_msg: list = []
                    tool_events: list = []
                    for tu in tool_uses:
                        async for sse_line in execute_tool_call(
                            tool_use=tu,
                            user_id=user_id,
                            can_see_internal=can_see_internal,
                            tool_error_counts=tool_error_counts,
                            tool_results_msg=tool_results_msg,
                            tool_events=tool_events,
                            all_entities=all_entities,
                        ):
                            yield sse_line

                    tools_json = json.dumps(tool_events, ensure_ascii=False, default=str)
                    await asyncio.to_thread(
                        save_message, session_id, "assistant", final_content, tools_json,
                    )
                    await asyncio.to_thread(
                        save_message, session_id, "user", tool_results_msg,
                    )

                    history.append({"role": "user", "content": tool_results_msg})
                    continue

                # Final assistant text (no more tool calls) — persist it
                await asyncio.to_thread(save_message, session_id, "assistant", final_content)
                break

            else:
                # for-loop exhausted MAX_TOOL_ROUNDS without a `break` — the LLM
                # was still calling tools on the last iteration and never produced
                # a text response. Inject a system hint and force one final synthesis
                # call with tools disabled so the user always gets an answer.
                logger.warning(
                    "Tool round limit reached for session %s; forcing synthesis", session_id
                )
                synthesis_hint = [{
                    "role": "user",
                    "content": (
                        f"[系统：已达最大工具调用轮次（{MAX_TOOL_ROUNDS}轮）。"
                        "请直接用中文总结以上所有工具调用结果，回答用户的问题，不要再调用任何工具。]"
                    ),
                }]
                synthesis_content = None
                async for event_type, payload in stream_with_fallback(
                    client, history + synthesis_hint, model, usage_accum,
                    system_prompt=active_system_prompt,
                    tools=[],  # disable tools — text-only response
                ):
                    if event_type == "chunk":
                        yield sse("chunk", content=payload)
                    elif event_type == "error":
                        yield sse("error", message=payload)
                        yield sse_done()
                        return
                    elif event_type == "_end":
                        synthesis_content = payload.get("content")
                if synthesis_content:
                    await asyncio.to_thread(
                        save_message, session_id, "assistant", synthesis_content
                    )

        # Persist extracted entities fire-and-forget — don't block the response.
        if all_entities:
            t = asyncio.create_task(asyncio.to_thread(save_entities, session_id, all_entities))
            _bg_tasks.add(t)
            t.add_done_callback(_bg_tasks.discard)

        credits_charged, balance_remaining = await charge_turn(
            user_id=user_id,
            session_id=session_id,
            model=model,
            usage_accum=usage_accum,
            is_admin=bool(req.is_admin),
        )

        yield sse(
            "usage",
            model=model.id,
            input_tokens=usage_accum.get("input_tokens", 0),
            output_tokens=usage_accum.get("output_tokens", 0),
            credits_charged=credits_charged,
            balance=balance_remaining,
        )
        yield sse_done()

    except httpx.TimeoutException:
        yield sse("error", message="请求超时，请点击重试。", retryable=True)
        yield sse_done()
    except Exception as e:
        logger.exception("Chat error")
        yield sse(
            "error",
            message="系统遇到临时故障，请点击重试。",
            retryable=True,
            detail=str(e)[:200],
        )
        yield sse_done()


# ─────────────────────────────────────────────────────────────
# Plan-only phase
# ─────────────────────────────────────────────────────────────

async def stream_plan_only(req):
    """Phase 1 stream: generate a plan proposal, emit one SSE event, done.

    Falls back to :func:`stream_chat` if the planner LLM returns no plan.
    """
    model = resolve_model(req.model_id)
    history = await asyncio.to_thread(load_history, req.session_id)

    # Ensure the session exists, but DON'T save the user message yet —
    # only save it after we know whether planner succeeds. This prevents
    # double-save if planner fails and we fall back to stream_chat (which
    # saves the user message itself).
    if req.user_id:
        await asyncio.to_thread(ensure_session, req.session_id, req.user_id)

    plan = await planner_mod.generate_plan(req.message, history, model)

    if plan is None:
        logger.warning("Planner returned no plan; falling back to normal execution")
        fallback_req = req.model_copy(update={"plan_mode": "off"})
        async for chunk in stream_chat(fallback_req):
            yield chunk
        return

    # Planner succeeded — commit to the plan flow, save user msg.
    if req.user_id:
        await asyncio.to_thread(save_message, req.session_id, "user", req.message)

    usage = plan.pop("_usage", {}) or {}
    credits_charged, balance_remaining = 0.0, None
    if req.user_id and not req.is_admin:
        try:
            credits_charged, balance_remaining = await charge_turn(
                user_id=req.user_id,
                session_id=req.session_id,
                model=model,
                usage_accum=usage,
                is_admin=bool(req.is_admin),
            )
        except Exception:
            logger.exception("Failed to record planner usage")

    # Persist the plan as a placeholder assistant message so it survives reload.
    # "kind": "plan_card" is an explicit marker used by load_history to skip
    # this row when building LLM context (plan cards are UI-only artifacts).
    if req.user_id:
        await asyncio.to_thread(
            save_message,
            req.session_id,
            "assistant",
            "",
            json.dumps(
                {"kind": "plan_card", "plan": plan, "original_message": req.message},
                ensure_ascii=False,
            ),
        )

    yield sse("plan_proposal", plan=plan, original_message=req.message)
    if credits_charged:
        yield sse("usage", credits_charged=credits_charged, balance=balance_remaining)
    yield sse_done()
