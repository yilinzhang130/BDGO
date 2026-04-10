"""
LLM helper — minimal synchronous wrapper around MiniMax (Anthropic-compatible API).

Used by report services via ReportContext.llm(). For streaming + tool_use, see chat.py.
"""

from __future__ import annotations

import logging

import httpx

from config import MINIMAX_ANTHROPIC_VERSION, MINIMAX_KEY, MINIMAX_MODEL, MINIMAX_URL

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0


def call_llm_sync(
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    model: str = MINIMAX_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Call MiniMax non-streaming, return final assistant text.

    Args:
        system: system prompt
        messages: [{"role": "user"|"assistant", "content": str}, ...]
        max_tokens: response token budget
    Returns:
        concatenated text from all `text` content blocks (ignoring `thinking` blocks)
    Raises:
        RuntimeError on API failure
    """
    body = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    headers = {
        "x-api-key": MINIMAX_KEY,
        "Content-Type": "application/json",
        "anthropic-version": MINIMAX_ANTHROPIC_VERSION,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(MINIMAX_URL, json=body, headers=headers)
    except httpx.TimeoutException as e:
        raise RuntimeError(f"LLM request timed out after {timeout}s") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"LLM HTTP error: {e}") from e

    if resp.status_code != 200:
        raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"LLM response JSON parse error: {e}") from e

    # MiniMax/Anthropic returns content as an array of blocks.
    # Each block is either {"type": "text", "text": "..."} or {"type": "thinking", ...}.
    content_blocks = data.get("content", [])
    texts = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text", "")
            if t:
                texts.append(t)

    if not texts:
        logger.warning("LLM returned no text blocks. Full response: %s", data)
        return ""

    return "\n".join(texts)
