"""Quick-search mode: single-turn web search + LLM summary with citations.

Contrast with the main agent loop (streaming.py): no tool-use loop, no CRM
lookups, no planning. Just Tavily → summarize. Lower latency, good for
news/fact lookups.
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from models import resolve_model
from services.external.search import search_web

from .billing import charge_turn
from .chat_store import ensure_session, load_history, save_message
from .llm_stream import stream_with_fallback
from .sse import sse, sse_done

logger = logging.getLogger(__name__)


QUICK_SEARCH_SYSTEM_PROMPT = """你是BDGO的快速搜索助手，帮助生命科学BD人员快速查询公开信息。

工作方式：
1. 下方提供了 Tavily 搜索结果（编号来源）。仅基于这些来源作答。
2. 回答中必须用 [1][2] 这种方式标注引用来源，标注在对应陈述的句末。
3. 如果来源信息不足以回答，诚实说明"公开资料有限"，不要编造。
4. 中文回答，简洁直接，必要时用列表/表格。不要用"根据搜索结果"这类废话开头。
5. 如果用户的问题涉及到深度分析、CRM数据查询、或报告生成，建议他们切换到 Agent 模式。"""


def _format_sources(sources: list[dict]) -> str:
    """Render Tavily results as numbered context block for the LLM."""
    if not sources:
        return "（无搜索结果）"
    lines = []
    for i, s in enumerate(sources, 1):
        title = (s.get("title") or "").strip()
        url = (s.get("url") or "").strip()
        snippet = (s.get("snippet") or "").strip()
        lines.append(f"[{i}] {title}\n    URL: {url}\n    {snippet}")
    return "\n\n".join(lines)


async def stream_quick_search(req):
    """Quick-search streaming handler — yields SSE-formatted strings."""
    session_id = req.session_id
    user_id = req.user_id
    model = resolve_model(req.model_id)
    usage_accum = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}

    if user_id:
        await asyncio.to_thread(ensure_session, session_id, user_id)

    # Persist the user message immediately (same as stream_chat).
    if user_id:
        await asyncio.to_thread(save_message, session_id, "user", req.message)

    # Search off the event loop — search_web is synchronous httpx.
    try:
        sources = await asyncio.to_thread(search_web, req.message, 8)
    except Exception:
        logger.exception("Quick-search Tavily call failed")
        sources = []

    yield sse("quick_sources", sources=sources)

    # Build single-turn history: prior turns for short-term memory + this query.
    history = await asyncio.to_thread(load_history, session_id)
    history = [m for m in history if isinstance(m.get("content"), str)][-6:]
    context_block = _format_sources(sources)
    user_prompt = f"用户问题：{req.message}\n\n搜索结果：\n{context_block}"
    history.append({"role": "user", "content": user_prompt})

    final_text_parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async for event_type, payload in stream_with_fallback(
                client,
                history,
                model,
                usage_accum,
                system_prompt=QUICK_SEARCH_SYSTEM_PROMPT,
                tools=[],
            ):
                if event_type == "chunk":
                    final_text_parts.append(payload)
                    yield sse("chunk", content=payload)
                elif event_type == "error":
                    yield sse("error", message=payload)
                    yield sse_done()
                    return
                # tool_call_start / _end are not meaningful without tools

        final_text = "".join(final_text_parts)
        if final_text.strip():
            # Save as structured content so it round-trips through load_history
            # the same way regular assistant turns do.
            await asyncio.to_thread(
                save_message,
                session_id,
                "assistant",
                [{"type": "text", "text": final_text}],
                json.dumps({"kind": "quick_search", "sources": sources}, ensure_ascii=False),
            )

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
        logger.exception("Quick-search error")
        yield sse(
            "error",
            message="系统遇到临时故障，请点击重试。",
            retryable=True,
            detail=str(e)[:200],
        )
        yield sse_done()
