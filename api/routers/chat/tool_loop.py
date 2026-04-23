"""Tool-use round execution: run each tool_use block, emit SSE events,
apply the per-tool circuit breaker, extract context entities.

Kept as mutating helpers rather than pure functions so the caller's
loop stays linear and readable — the state that needs to persist
across rounds (tool_error_counts, all_entities, history tool_results)
is passed in and mutated in place.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .entities import extract_context_entities
from .sse import sse, sse_raw
from .tools import REPORT_TOOL_NAME_TO_SLUG, TOOL_IMPL, execute_tool
from .tools.registry import TOOL_FAILED_KEY


async def execute_tool_call(
    *,
    tool_use: dict,
    user_id: int | None,
    can_see_internal: bool,
    tool_error_counts: dict[str, int],
    tool_results_msg: list,
    tool_events: list,
    all_entities: list,
) -> AsyncIterator[str]:
    """Execute one ``tool_use`` block, yield SSE strings for client.

    Mutates the supplied lists in place:
      * ``tool_error_counts`` — consecutive-failure counter by tool name
      * ``tool_results_msg`` — appends the ``tool_result`` history block
      * ``tool_events`` — appends a persistence-friendly tool summary
      * ``all_entities`` — appends any context entities extracted
    """
    name = tool_use["name"]
    inp = tool_use.get("input") or {}

    # execute_tool runs synchronous CRM/DB queries — offload to a thread
    # so the event loop stays free for other concurrent SSE streams.
    result_str = await asyncio.to_thread(
        execute_tool,
        TOOL_IMPL,
        name,
        inp,
        user_id=user_id,
        can_see_internal=can_see_internal,
    )

    # Parse once — reused for circuit-breaker, report_task, and entity
    # extraction below.
    try:
        result_obj = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        result_obj = None

    # Circuit-breaker: stop retrying a tool that fails twice.
    if isinstance(result_obj, dict) and result_obj.get(TOOL_FAILED_KEY):
        tool_error_counts[name] = tool_error_counts.get(name, 0) + 1
        if tool_error_counts[name] >= 2:
            result_str = json.dumps(
                {
                    "error": result_obj.get("error", "工具执行失败"),
                    "instruction": (
                        "此工具已连续失败，请停止调用它，"
                        "直接用中文告知用户遇到了技术问题并结束本次任务。"
                    ),
                },
                ensure_ascii=False,
            )
            result_obj = json.loads(result_str)
    else:
        tool_error_counts.pop(name, None)

    yield sse("tool_result", name=name)

    if (
        name in REPORT_TOOL_NAME_TO_SLUG
        and isinstance(result_obj, dict)
        and result_obj.get("status") == "queued"
        and result_obj.get("task_id")
    ):
        yield sse(
            "report_task",
            task_id=result_obj["task_id"],
            slug=REPORT_TOOL_NAME_TO_SLUG[name],
            estimated_seconds=result_obj.get("estimated_seconds", 60),
        )

    tool_events.append(
        {
            "name": name,
            "input": inp,
            "result_preview": result_str[:500],
        }
    )

    for entity in extract_context_entities(name, result_str):
        # ``entity`` dicts already include a ``type`` key (e.g. "context_entity").
        yield sse_raw(entity)
        all_entities.append(entity)

    tool_results_msg.append(
        {
            "type": "tool_result",
            "tool_use_id": tool_use["id"],
            "content": result_str,
        }
    )
