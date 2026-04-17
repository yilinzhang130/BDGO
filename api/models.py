"""
models.py — LLM model registry.

Each model has:
  - A display name for UI
  - API endpoint + auth (currently all MiniMax; extend as needed)
  - Credit weights (input / output tokens) — relative cost multiplier

Credit formula (see credits.py):
    credits = input_tokens * input_weight + output_tokens * output_weight

Output tokens are ~4x input tokens in raw API cost for most providers, which we
reflect in the default weights. Context accumulation in long sessions (why some
chats cost much more than others — Manus-style) is handled naturally because
each turn re-sends the full history → input_tokens grows per turn.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import (
    MINIMAX_ANTHROPIC_VERSION,
    MINIMAX_KEY,
    MINIMAX_MODEL,
    MINIMAX_URL,
)


@dataclass(frozen=True)
class ModelSpec:
    id: str                 # stable identifier used in API/DB
    display_name: str       # shown in the model picker
    provider: str           # "minimax", "deepseek", ...
    api_url: str
    api_key: str
    api_model: str          # the exact model name for the provider
    anthropic_version: str | None
    # credit weights — per 1 token
    input_weight: float
    output_weight: float
    # Soft cap shown in UI ("max 80k context"); informational only
    context_note: str = ""


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────
# Start with MiniMax only — the one that works end-to-end today.
# Adding a new model = append a ModelSpec here. No other code changes.
#
# Weights are tuned so MiniMax M1 = 1.0 baseline credit/token.
# A hypothetical Claude Sonnet would be ~5x input, ~5x output, etc.

_MODELS: list[ModelSpec] = [
    ModelSpec(
        id="minimax-m1",
        display_name="MiniMax M1 (80k)",
        provider="minimax",
        api_url=MINIMAX_URL,
        api_key=MINIMAX_KEY,
        api_model=MINIMAX_MODEL,
        anthropic_version=MINIMAX_ANTHROPIC_VERSION,
        input_weight=1.0,
        output_weight=4.0,
        context_note="80k tokens",
    ),
    # Wired but disabled until DEEPSEEK_API_KEY is set in the VM env.
    ModelSpec(
        id="deepseek-v3",
        display_name="DeepSeek V3",
        provider="deepseek",
        api_url="https://api.deepseek.com/anthropic/v1/messages",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        api_model="deepseek-chat",
        anthropic_version="2023-06-01",
        input_weight=0.8,
        output_weight=3.2,
        context_note="64k tokens",
    ),
    # Placeholder: enable when CLAUDE_API_KEY is provided.
    ModelSpec(
        id="claude-sonnet",
        display_name="Claude Sonnet 4",
        provider="anthropic",
        api_url="https://api.anthropic.com/v1/messages",
        api_key=os.environ.get("CLAUDE_API_KEY", ""),
        api_model="claude-sonnet-4",
        anthropic_version="2023-06-01",
        input_weight=5.0,
        output_weight=25.0,
        context_note="200k tokens",
    ),
]

MODELS: dict[str, ModelSpec] = {m.id: m for m in _MODELS}
DEFAULT_MODEL_ID = "minimax-m1"
OVERLOAD_MSG = "所有AI服务当前负载较高，请稍后重试。"


def resolve_model(model_id: str | None) -> ModelSpec:
    """Return the requested model or the default. Never raises."""
    if model_id and model_id in MODELS:
        return MODELS[model_id]
    return MODELS[DEFAULT_MODEL_ID]


def fallback_chain(model_id: str) -> list[ModelSpec]:
    """Return available fallback models excluding model_id, cheapest first."""
    priority = ["deepseek-v3", "minimax-m1", "claude-sonnet"]
    return [
        MODELS[mid]
        for mid in priority
        if mid != model_id and mid in MODELS and MODELS[mid].api_key
    ]


def available_models() -> list[dict]:
    """JSON-serialisable list for the /api/models endpoint."""
    return [
        {
            "id": m.id,
            "display_name": m.display_name,
            "provider": m.provider,
            "input_weight": m.input_weight,
            "output_weight": m.output_weight,
            "context_note": m.context_note,
            "available": bool(m.api_key),
        }
        for m in _MODELS
    ]
