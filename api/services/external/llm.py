"""
LLM helper — minimal synchronous wrapper around MiniMax (Anthropic-compatible API).

Used by report services via ReportContext.llm(). For streaming + tool_use, see chat.py.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time

import httpx
from models import DEFAULT_MODEL_ID, MODELS, OVERLOAD_MSG, ModelSpec, fallback_chain

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
                        wait = (2**attempt) * (0.5 + random.random())
                        logger.warning(
                            "%s 529 overload (attempt %d/3), retrying in %.1fs",
                            model.id,
                            attempt + 1,
                            wait,
                        )
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
    model_id: str = DEFAULT_MODEL_ID,
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
    primary = MODELS.get(model_id) or MODELS[DEFAULT_MODEL_ID]
    models_to_try = [primary] + fallback_chain(primary.id)

    for model in models_to_try:
        result = _call_one_sync(model, system, messages, max_tokens, timeout)
        if result is None:
            logger.warning("Model %s overloaded, trying fallback", model.id)
            continue
        return result

    raise RuntimeError(OVERLOAD_MSG)


def _extract_json_object(text: str) -> dict | None:
    """Pull the first JSON object out of arbitrary LLM text. Tolerates markdown fences
    and surrounding commentary. Returns None if nothing parseable is found."""
    if not text:
        return None
    # Strip ```json ... ``` fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: grab the first {...} block by brace matching
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def extract_params_from_text(
    freeform_text: str,
    schema: dict,
    service_name: str,
    timeout: float = 30.0,
) -> dict:
    """Use the LLM to map freeform user text onto a JSON-schema-shaped param object.

    Returns the parsed object (may be partial — caller validates against the
    service's Pydantic model). Returns {} if the LLM can't produce anything usable.
    """
    if not freeform_text.strip():
        return {}

    props = schema.get("properties", {})
    required = schema.get("required", [])
    field_desc_lines = []
    for name, spec in props.items():
        marker = "(REQUIRED)" if name in required else "(optional)"
        desc = spec.get("description", "")
        t = spec.get("type", "string")
        field_desc_lines.append(f"- {name} {marker} [{t}]: {desc}")

    system = (
        f"You extract structured arguments for the '{service_name}' report service from "
        "Chinese or English user text. Respond with ONLY a JSON object containing the "
        "fields you can confidently extract from the user's text — omit fields you "
        "cannot determine. Do not invent values. Do not wrap in markdown fences.\n\n"
        "Available fields:\n" + "\n".join(field_desc_lines)
    )
    messages = [{"role": "user", "content": freeform_text.strip()}]

    try:
        raw = call_llm_sync(system=system, messages=messages, max_tokens=512, timeout=timeout)
    except Exception as e:
        logger.warning("extract_params_from_text: LLM call failed: %s", e)
        return {}

    obj = _extract_json_object(raw)
    if not isinstance(obj, dict):
        return {}
    # Only keep keys that are actually part of the schema — filter out hallucinated fields
    return {k: v for k, v in obj.items() if k in props}
