"""Two-layer context compaction to keep long sessions under the LLM's
token budget without losing meaningful history.

Layer 1 (cheap, always-on): strip non-text content blocks from messages
older than the last N user turns. Removes the bulk of token weight (old
tool_use / tool_result blobs) with no LLM call.

Layer 2 (on-demand): if layer 1 is still over budget, ask the summarizer
LLM to produce a short session brief that replaces the old turns. Brief
is cached in ``sessions.brief`` so subsequent turns reuse it until the
budget is exceeded again.
"""

from __future__ import annotations

import json
import logging

import planner as planner_mod
from models import ModelSpec

from .chat_store import get_session_brief, save_session_brief

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Tuning knobs
# ─────────────────────────────────────────────────────────────

KEEP_VERBATIM = 4  # last N user+assistant turns kept as-is
TOKEN_BUDGET = 40_000  # target tokens after layer 1
CHARS_PER_TOKEN = 2.5  # rough estimator for mixed CJK+ASCII


# ─────────────────────────────────────────────────────────────
# Estimation
# ─────────────────────────────────────────────────────────────


def estimate_tokens(history: list[dict]) -> int:
    """Cheap char-based token estimate for a history list."""
    total_chars = 0
    for m in history:
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if not isinstance(b, dict):
                    continue
                # text / tool_use input / tool_result content all count
                t = b.get("text")
                if isinstance(t, str):
                    total_chars += len(t)
                tr = b.get("content")
                if isinstance(tr, list):
                    for sub in tr:
                        if isinstance(sub, dict):
                            total_chars += len(sub.get("text", "") or "")
                elif isinstance(tr, str):
                    total_chars += len(tr)
                inp = b.get("input")
                if isinstance(inp, dict):
                    total_chars += len(json.dumps(inp, ensure_ascii=False))
        elif isinstance(c, str):
            total_chars += len(c)
    return int(total_chars / CHARS_PER_TOKEN)


# ─────────────────────────────────────────────────────────────
# Layer 1 — strip old tool blocks
# ─────────────────────────────────────────────────────────────


def strip_tool_blocks_from_old(
    history: list[dict],
    keep_last_n: int,
) -> list[dict]:
    """Strip non-text content blocks from messages older than the last
    ``keep_last_n`` user turns. Preserves tool_use/tool_result pairs in
    the recent zone so the LLM can still reason over them.
    """
    user_idx = [i for i, m in enumerate(history) if m.get("role") == "user"]
    if len(user_idx) <= keep_last_n:
        return history  # nothing to strip

    boundary = user_idx[-keep_last_n]  # messages before this are "old"

    result: list[dict] = []
    for i, m in enumerate(history):
        if i >= boundary:
            result.append(m)
            continue

        content = m.get("content")
        if isinstance(content, list):
            # Keep only text blocks in old zone
            text_blocks = [
                b
                for b in content
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
            ]
            if text_blocks:
                result.append({"role": m["role"], "content": text_blocks})
            # else: message was only tool_use/tool_result/empty — drop it
        elif isinstance(content, str) and content.strip():
            result.append(m)
        # else: empty — drop

    return result


# ─────────────────────────────────────────────────────────────
# Full pipeline (layer 1 + layer 2)
# ─────────────────────────────────────────────────────────────


async def compact_if_needed(
    session_id: str,
    history: list[dict],
    model: ModelSpec,
) -> list[dict]:
    """Apply layer-1 unconditionally; layer-2 only when still over budget.

    Returns the compacted history ready to pass to the LLM. Cached summary
    is reused across turns so we only pay the summarization cost once per
    high-watermark.
    """
    # Layer 1: always applied — cheap and reduces noise even when in budget
    compacted = strip_tool_blocks_from_old(history, KEEP_VERBATIM)

    # Fast path: within budget, just return layer-1 result
    est = estimate_tokens(compacted)
    if est <= TOKEN_BUDGET:
        return compacted

    # Layer 2: prepare the old turns (everything before the keep-verbatim
    # zone) plus any existing brief, ask the summarizer LLM to produce a
    # new brief.
    user_idx = [i for i, m in enumerate(compacted) if m.get("role") == "user"]
    if len(user_idx) <= KEEP_VERBATIM:
        return compacted  # can't compact further

    boundary = user_idx[-KEEP_VERBATIM]
    old_turns = compacted[:boundary]
    recent = compacted[boundary:]

    existing_brief, _ = get_session_brief(session_id)

    # Cheap cache-hit path: if a brief already exists and substituting it
    # for the old turns would be within budget, reuse it — no LLM call.
    if existing_brief:
        estimated_with_cached = estimate_tokens(
            [{"role": "user", "content": existing_brief}] + recent
        )
        if estimated_with_cached <= TOKEN_BUDGET:
            return [_wrap_brief(existing_brief)] + recent

    # Otherwise regenerate brief incorporating old_turns + prior brief.
    new_brief = await planner_mod.summarize_history(old_turns, existing_brief, model)
    if not new_brief:
        # Summarizer failed — fall back to layer-1 only
        return compacted

    # Cache the new brief (idempotent across turns)
    save_session_brief(session_id, new_brief, None)

    return [_wrap_brief(new_brief)] + recent


def _wrap_brief(brief: str) -> dict:
    """Format a raw brief string as a user turn the LLM understands."""
    return {
        "role": "user",
        "content": (f"[会话早前内容的摘要，供你参考]\n{brief}\n\n[以下是最近几轮对话的原文]"),
    }
