"""
LLM helper — minimal synchronous wrapper around MiniMax (Anthropic-compatible API).

Used by report services via ReportContext.llm(). For streaming + tool_use, see chat.py.
"""

from __future__ import annotations

import logging
import time

import httpx

from models import MODELS, ModelSpec, fallback_chain

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0


def _call_one_sync(
    model: ModelSpec,
    system: str,
    messages: list[dict],
    max_tokens: int,
    timeout: float,
) -> str | None:
    """Single provider attempt. Returns text on success, None on 529 overload, raises on other errors."""
    body = {
        "model": model.api_model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    headers = {
        "x-api-key": model.api_key,
        "Content-Type": "application/json",
    }
    if model.anthropic_version:
        headers["anthropic-version"] = model.anthropic_version

    resp = None
    try:
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(3):
                try:
                    resp = client.post(model.api_url, json=body, headers=headers)
                except httpx.TimeoutException as e:
                    raise RuntimeError(f"LLM request timed out after {timeout}s") from e
                except httpx.HTTPError as e:
                    raise RuntimeError(f"LLM HTTP error: {e}") from e

                if resp.status_code == 529:
                    if attempt < 2:
                        wait = 2 ** attempt
                        logger.warning("%s 529 overload (attempt %d/3), retrying in %ds", model.id, attempt + 1, wait)
                        time.sleep(wait)
                        continue
                    return None  # signal overload to caller for fallback
                break
    except RuntimeError:
        raise

    if resp is None or resp.status_code != 200:
        raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"LLM response JSON parse error: {e}") from e

    content_blocks = data.get("content", [])
    texts = [
        block["text"]
        for block in content_blocks
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
    ]
    if not texts:
        logger.warning("LLM returned no text blocks. Full response: %s", data)
        return ""
    return "\n".join(texts)


def call_llm_sync(
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    model_id: str = "minimax-m1",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Call LLM non-streaming, return final assistant text.

    Falls back to alternative providers if the primary returns 529 overloaded.

    Args:
        system: system prompt
        messages: [{"role": "user"|"assistant", "content": str}, ...]
        max_tokens: response token budget
        model_id: key from models.MODELS (default: minimax-m1)
    Returns:
        concatenated text from all `text` content blocks
    Raises:
        RuntimeError on API failure or all providers overloaded
    """
    primary = MODELS.get(model_id) or MODELS["minimax-m1"]
    models_to_try = [primary] + fallback_chain(primary.id)

    for model in models_to_try:
        result = _call_one_sync(model, system, messages, max_tokens, timeout)
        if result is None:
            logger.warning("Model %s overloaded, trying fallback", model.id)
            continue
        return result

    raise RuntimeError("所有AI服务当前负载较高，请稍后重试")
