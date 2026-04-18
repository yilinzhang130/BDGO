"""LLM streaming core: tool-use loop, plan-only phase, SSE framing."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

import credits as credits_mod
import planner as planner_mod
from models import OVERLOAD_MSG, ModelSpec, fallback_chain, resolve_model

from .attachments import extract_text
from .compaction import compact_if_needed
from .entities import extract_context_entities
from .session_store import (
    ensure_session,
    load_history,
    save_entities,
    save_message,
)
from .system_prompt import SYSTEM_PROMPT
from .tools import REPORT_TOOL_NAME_TO_SLUG, TOOL_IMPL, TOOLS, execute_tool
from .tools.registry import TOOL_FAILED_KEY

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# LLM streaming wrapper
# ─────────────────────────────────────────────────────────────

async def call_minimax_stream(
    client: httpx.AsyncClient,
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
    headers = {
        "x-api-key": model.api_key,
        "Content-Type": "application/json",
    }
    if model.anthropic_version:
        headers["anthropic-version"] = model.anthropic_version

    collected_content: list = []
    current_tool_use: dict | None = None
    current_text = ""
    stop_reason = None

    # 529 = server overloaded — retry up to 3 times with backoff
    max_retries = 3
    for attempt in range(max_retries):
        async with client.stream("POST", model.api_url, json=body, headers=headers) as resp:
            if resp.status_code == 529:
                await resp.aread()
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "MiniMax 529 (attempt %d/%d), retry in %ds",
                        attempt + 1, max_retries, wait,
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
                elif 500 <= resp.status_code < 600:
                    msg = "AI服务暂时不可用，请稍后重试。"
                else:
                    msg = f"AI服务异常（{resp.status_code}），请稍后重试。"
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
                            collected_content.append({
                                "type": "tool_use",
                                "id": current_tool_use["id"],
                                "name": current_tool_use["name"],
                                "input": inp,
                            })
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

        yield ("_end", {"stop_reason": stop_reason, "content": collected_content})
        return


# ─────────────────────────────────────────────────────────────
# Fallback wrapper — tries primary model then alternatives on 529
# ─────────────────────────────────────────────────────────────

async def _stream_with_fallback(
    client: httpx.AsyncClient,
    messages: list,
    model: ModelSpec,
    usage_accum: dict,
    system_prompt: str | None = None,
    tools: list | None = None,
):
    """Wrap call_minimax_stream with cross-provider fallback on overload.

    If the primary model signals overloaded (529 exhausted), tries each
    model in fallback_chain() before giving up.
    """
    models_to_try = [model] + fallback_chain(model.id)
    for try_model in models_to_try:
        async for event_type, payload in call_minimax_stream(
            client, messages, try_model, usage_accum, system_prompt, tools
        ):
            if event_type == "overloaded":
                logger.warning("Model %s overloaded, trying fallback", try_model.id)
                break
            yield event_type, payload
        else:
            return  # inner loop finished without break → success
    yield ("error", OVERLOAD_MSG)


# ─────────────────────────────────────────────────────────────
# Main chat handler
# ─────────────────────────────────────────────────────────────

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
        ensure_session(session_id, user_id)

    history = load_history(session_id)

    # When executing a confirmed plan, the user message + empty plan
    # placeholder are already in history from the planner phase. Strip
    # trailing empty assistant turns so the LLM sees the user prompt as
    # the latest turn, then skip re-appending + re-saving below.
    is_executing_plan = req.plan_confirm is not None
    if is_executing_plan:
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

    user_text = req.message
    attachments_json = None
    if req.file_ids:
        # Extract all attachments concurrently — each PDF may run OCR
        # (seconds of blocking CPU), so a sequential loop is O(N * OCR).
        extracted_list = await asyncio.gather(
            *(asyncio.to_thread(extract_text, fid) for fid in req.file_ids)
        )
        attachment_parts = []
        failed_extractions = []
        for fid, extracted in zip(req.file_ids, extracted_list):
            if extracted:
                logger.info("Extracted %d chars from attachment: %s", len(extracted), fid)
                attachment_parts.append(f"\n\n[附件内容: {fid}]\n{extracted}")
            else:
                logger.warning("Failed to extract content from attachment: %s", fid)
                failed_extractions.append(fid)

        if attachment_parts:
            user_text = req.message + "".join(attachment_parts)
            user_text += (
                "\n\n[系统指令：用户上传了文件，文件内容已在上方提供。请立即执行以下步骤："
                "1) 从文件内容中提取公司名、资产名、靶点、适应症等关键实体；"
                "2) 用提取的实体并行调用 search_companies、search_assets、search_clinical、search_deals 查询CRM数据；"
                "3) 如果文件涉及特定疾病，调用 query_treatment_guidelines 查询治疗格局；"
                "4) 综合文件内容和CRM数据，输出结构化分析报告（公司画像、管线评估、治疗格局、交易参考、BD建议）。"
                "不要只总结文件内容，必须交叉验证CRM数据。]"
            )
        elif failed_extractions:
            user_text = req.message + (
                f"\n\n[系统提示：用户上传了文件 {', '.join(failed_extractions)}，"
                "但文件内容无法提取（可能是加密PDF或格式不支持）。"
                "请直接告知用户文件无法解析，并询问他们能否提供文字版或核心信息。]"
            )
        attachments_json = json.dumps(req.file_ids)

    if not is_executing_plan:
        history.append({"role": "user", "content": user_text})
        save_message(session_id, "user", user_text, attachments_json=attachments_json)

    # Auto-compact: strip old tool blocks; summarize if still over budget.
    history = await compact_if_needed(session_id, history, model)

    all_entities: list[dict] = []
    # Per-request tool error counter: tool_name → consecutive failure count.
    # If any tool fails twice in a row, we inject a stop hint so the LLM
    # doesn't burn all 8 rounds retrying the same broken tool.
    tool_error_counts: dict[str, int] = {}

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            for _iteration in range(8):  # up to 8 tool-call rounds
                final_content = None
                final_stop_reason = None

                async for event_type, payload in _stream_with_fallback(
                    client, history, model, usage_accum,
                    system_prompt=active_system_prompt,
                ):
                    if event_type == "chunk":
                        yield f"data: {json.dumps({'type': 'chunk', 'content': payload})}\n\n"
                    elif event_type == "tool_call_start":
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': payload['name']})}\n\n"
                    elif event_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'message': payload})}\n\n"
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return
                    elif event_type == "_end":
                        final_content = payload["content"]
                        final_stop_reason = payload["stop_reason"]

                if final_content is None:
                    break

                history.append({"role": "assistant", "content": final_content})

                tool_uses = [b for b in final_content if b.get("type") == "tool_use"]
                if final_stop_reason == "tool_use" and tool_uses:
                    tool_results_msg = []
                    tool_events = []
                    for tu in tool_uses:
                        name = tu["name"]
                        inp = tu.get("input") or {}
                        result_str = execute_tool(
                            TOOL_IMPL, name, inp,
                            user_id=user_id,
                            can_see_internal=can_see_internal,
                        )

                        # Parse once — reused for circuit-breaker, report_task,
                        # and entity extraction below.
                        try:
                            result_obj = json.loads(result_str)
                        except (json.JSONDecodeError, TypeError):
                            result_obj = None

                        # Circuit-breaker: stop retrying a tool that fails twice.
                        if isinstance(result_obj, dict) and result_obj.get(TOOL_FAILED_KEY):
                            tool_error_counts[name] = tool_error_counts.get(name, 0) + 1
                            if tool_error_counts[name] >= 2:
                                result_str = json.dumps({
                                    "error": result_obj.get("error", "工具执行失败"),
                                    "instruction": (
                                        "此工具已连续失败，请停止调用它，"
                                        "直接用中文告知用户遇到了技术问题并结束本次任务。"
                                    ),
                                }, ensure_ascii=False)
                                result_obj = json.loads(result_str)
                        else:
                            tool_error_counts.pop(name, None)

                        yield f"data: {json.dumps({'type': 'tool_result', 'name': name})}\n\n"

                        if (
                            name in REPORT_TOOL_NAME_TO_SLUG
                            and isinstance(result_obj, dict)
                            and result_obj.get("status") == "queued"
                            and result_obj.get("task_id")
                        ):
                            yield (
                                "data: "
                                + json.dumps({
                                    "type": "report_task",
                                    "task_id": result_obj["task_id"],
                                    "slug": REPORT_TOOL_NAME_TO_SLUG[name],
                                    "estimated_seconds": result_obj.get("estimated_seconds", 60),
                                })
                                + "\n\n"
                            )

                        tool_events.append({
                            "name": name,
                            "input": inp,
                            "result_preview": result_str[:500],
                        })

                        for entity in extract_context_entities(name, result_str):
                            yield f"data: {json.dumps(entity, ensure_ascii=False)}\n\n"
                            all_entities.append(entity)

                        tool_results_msg.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result_str,
                        })

                    tools_json = json.dumps(tool_events, ensure_ascii=False, default=str)
                    save_message(session_id, "assistant", final_content, tools_json=tools_json)
                    save_message(session_id, "user", tool_results_msg)

                    history.append({"role": "user", "content": tool_results_msg})
                    continue

                # Final assistant text (no more tool calls) — persist it
                save_message(session_id, "assistant", final_content)
                break

        # Persist all extracted context entities
        save_entities(session_id, all_entities)

        # ── Bill credits (success path only) ──────────────────
        # All error paths `return` before reaching here, so a failed
        # turn is never charged. Admin users are never billed.
        credits_charged = 0.0
        balance_remaining = None
        if user_id and not req.is_admin:
            credits_charged = credits_mod.record_usage(
                user_id=user_id,
                session_id=session_id,
                model_id=model.id,
                input_tokens=usage_accum.get("input_tokens", 0),
                output_tokens=usage_accum.get("output_tokens", 0),
                input_weight=model.input_weight,
                output_weight=model.output_weight,
            )
            try:
                balance_info = credits_mod.get_balance(user_id)
                balance_remaining = balance_info["balance"]
            except Exception:
                balance_remaining = None

        yield (
            "data: "
            + json.dumps({
                "type": "usage",
                "model": model.id,
                "input_tokens": usage_accum.get("input_tokens", 0),
                "output_tokens": usage_accum.get("output_tokens", 0),
                "credits_charged": credits_charged,
                "balance": balance_remaining,
            })
            + "\n\n"
        )
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except httpx.TimeoutException:
        yield f"data: {json.dumps({'type': 'error', 'message': '请求超时，请点击重试。', 'retryable': True})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        logger.exception("Chat error")
        yield f"data: {json.dumps({'type': 'error', 'message': '系统遇到临时故障，请点击重试。', 'retryable': True, 'detail': str(e)[:200]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ─────────────────────────────────────────────────────────────
# Plan-only phase
# ─────────────────────────────────────────────────────────────

async def stream_plan_only(req):
    """Phase 1 stream: generate a plan proposal, emit one SSE event, done.

    Falls back to ``stream_chat`` if the planner LLM returns no plan.
    """
    model = resolve_model(req.model_id)
    history = load_history(req.session_id)

    # Ensure the session exists, but DON'T save the user message yet —
    # only save it after we know whether planner succeeds. This prevents
    # double-save if planner fails and we fall back to stream_chat (which
    # saves the user message itself).
    if req.user_id:
        ensure_session(req.session_id, req.user_id)

    plan = await planner_mod.generate_plan(req.message, history, model)

    if plan is None:
        # Planner failed — fall through to normal execution.
        logger.warning("Planner returned no plan; falling back to normal execution")
        fallback_req = req.model_copy(update={"plan_mode": "off"})
        async for chunk in stream_chat(fallback_req):
            yield chunk
        return

    # Planner succeeded — commit to the plan flow, save user msg.
    if req.user_id:
        save_message(req.session_id, "user", req.message)

    # Bill planner tokens (admins skip)
    usage = plan.pop("_usage", {}) or {}
    credits_charged = 0.0
    balance_remaining = None
    if req.user_id and not req.is_admin:
        try:
            credits_charged = credits_mod.record_usage(
                user_id=req.user_id,
                session_id=req.session_id,
                model_id=model.id,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                input_weight=model.input_weight,
                output_weight=model.output_weight,
            )
            balance_remaining = credits_mod.get_balance(req.user_id)["balance"]
        except Exception:
            logger.exception("Failed to record planner usage")

    # Persist the plan as a placeholder assistant message so it survives reload.
    # "kind": "plan_card" is an explicit marker used by load_history to skip
    # this row when building LLM context (plan cards are UI-only artifacts).
    if req.user_id:
        save_message(
            req.session_id,
            "assistant",
            "",
            tools_json=json.dumps(
                {"kind": "plan_card", "plan": plan, "original_message": req.message},
                ensure_ascii=False,
            ),
        )

    yield (
        "data: "
        + json.dumps(
            {"type": "plan_proposal", "plan": plan, "original_message": req.message},
            ensure_ascii=False,
        )
        + "\n\n"
    )
    if credits_charged:
        yield (
            "data: "
            + json.dumps({
                "type": "usage",
                "credits_charged": credits_charged,
                "balance": balance_remaining,
            })
            + "\n\n"
        )
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
