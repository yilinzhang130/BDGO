"""
LLM helper — minimal synchronous wrapper around MiniMax (Anthropic-compatible API).

Used by report services via ReportContext.llm(). For streaming + tool_use, see chat.py.
"""

from __future__ import annotations

import atexit
import json
import logging
import random
import re
import time

import httpx
from models import DEFAULT_MODEL_ID, MODELS, OVERLOAD_MSG, ModelSpec, fallback_chain

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0

# Shared sync HTTP client — avoids a fresh TCP+TLS handshake for every report
# chapter. buyer_profile now runs up to 6 parallel chapters across 2 batches
# (max_workers=2 + max_workers=4) and up to REPORT_MAX_WORKERS=6 concurrent
# reports, giving a worst-case of 6×4 = 24 simultaneous LLM threads. Set
# max_connections=40 so threads never queue for a connection and nullify the
# parallelism benefit. Timeout is set per-request by callers.
_http_client = httpx.Client(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
)
atexit.register(_http_client.close)


def _call_one_sync(
    model: ModelSpec,
    system: str,
    messages: list[dict],
    max_tokens: int,
    timeout: float,
    label: str = "",
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
    t0 = time.monotonic()
    try:
        for attempt in range(3):
            try:
                resp = _http_client.post(model.api_url, json=body, headers=headers, timeout=timeout)
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

    usage = data.get("usage", {})
    logger.info(
        "llm_call model=%s key=...%s in=%d out=%d cache_read=%d latency_ms=%d status=ok%s",
        model.id,
        (model.api_key or "")[-6:],
        int(usage.get("input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
        int(usage.get("cache_read_input_tokens") or 0),
        int((time.monotonic() - t0) * 1000),
        f" label={label}" if label else "",
    )

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
    label: str = "",
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
        result = _call_one_sync(model, system, messages, max_tokens, timeout, label=label)
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


# key=value pair extractor. Three forms recognised: key="quoted with spaces",
# key='single quoted', and bare key=unquoted_token. Only keys present in
# ``schema_props`` survive — protects against the LLM-only path's
# hallucinated-field problem and against accidental injection from stray
# text that happens to contain ``=`` signs.
_KV_PATTERN = re.compile(
    r"""
    \b(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)   # identifier-style key
    =
    (?:
        "(?P<dq>[^"]*)"                  # double-quoted value
      | '(?P<sq>[^']*)'                  # single-quoted value
      | (?P<bare>[^\s"']+)               # bare token: stop at whitespace or quote
    )
    """,
    re.VERBOSE,
)


def _coerce_kv_value(raw: str, spec: dict):
    """Coerce a string match to the type declared in JSON Schema.

    Falls back to the raw string for unknown / unparseable types — the
    caller's Pydantic model will raise a clear validation error rather
    than us silently mangling intent.
    """
    t = spec.get("type", "string")
    if t == "boolean":
        low = raw.lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
        return raw
    if t == "integer":
        try:
            return int(raw)
        except ValueError:
            return raw
    if t == "number":
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def extract_kv_pairs(text: str, schema_props: dict) -> tuple[dict, str]:
    """Pre-LLM deterministic parser for chip-style `key=value` slash commands.

    Chip handoffs (e.g. `/legal contract_type=spa source_task_id=abc123
    counterparty="Pfizer"`) emit explicit key=value pairs — sending those
    through an LLM is wasted latency + a hallucination risk. This helper
    extracts them deterministically, leaving any non-matching text as
    residual for the LLM to handle when the user mixed chip and free text.

    Returns:
        (kv_params, residual_text) — kv_params holds schema-valid fields,
        residual_text is everything not consumed by a kv match (suitable
        for the LLM fallback to extract free-text fields from).
    """
    if not text:
        return {}, ""

    parsed: dict = {}
    consumed_spans: list[tuple[int, int]] = []
    for m in _KV_PATTERN.finditer(text):
        key = m.group("key")
        if key not in schema_props:
            continue  # skip stray identifiers — defends against typos / injection
        raw_value = m.group("dq")
        if raw_value is None:
            raw_value = m.group("sq")
        if raw_value is None:
            raw_value = m.group("bare") or ""
        parsed[key] = _coerce_kv_value(raw_value, schema_props[key])
        consumed_spans.append(m.span())

    # Build residual by removing all matched spans (in reverse so indices stay valid)
    residual_chars = list(text)
    for start, end in sorted(consumed_spans, reverse=True):
        del residual_chars[start:end]
    residual = "".join(residual_chars).strip()

    return parsed, residual


def extract_params_from_text(
    freeform_text: str,
    schema: dict,
    service_name: str,
    timeout: float = 30.0,
) -> dict:
    """Map freeform user text onto a JSON-schema-shaped param object.

    Strategy:
      1. Deterministic key=value pre-parse for chip-style structured args
         (no LLM call when the input is fully structured).
      2. If residual text remains, fall back to the LLM extractor for the
         free-text portion. LLM-extracted fields don't override anything
         the deterministic parser already locked in.

    Returns the merged dict (may be partial — caller validates against
    the service's Pydantic model). Returns {} if both paths fail.
    """
    if not freeform_text.strip():
        return {}

    props = schema.get("properties", {})
    required = schema.get("required", [])

    # 1. Deterministic kv pre-parse — handles chip-emitted commands without
    #    an LLM round-trip
    kv_params, residual = extract_kv_pairs(freeform_text, props)
    if kv_params and not residual:
        # Pure chip command — done; skip the LLM call entirely
        return kv_params

    # 2. LLM fallback for residual free-text portion
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
    # Send only the residual to the LLM (kv-matched parts already locked in)
    llm_input = (residual or freeform_text).strip()
    messages = [{"role": "user", "content": llm_input}]

    try:
        raw = call_llm_sync(system=system, messages=messages, max_tokens=512, timeout=timeout)
    except Exception as e:
        logger.warning("extract_params_from_text: LLM call failed: %s", e)
        # Even if LLM fails, return whatever the deterministic parser found
        return kv_params

    obj = _extract_json_object(raw)
    if not isinstance(obj, dict):
        return kv_params
    # Only keep keys in schema (filter hallucinated fields). kv_params wins on
    # collision — they came from explicit user/chip intent.
    llm_params = {k: v for k, v in obj.items() if k in props}
    return {**llm_params, **kv_params}
