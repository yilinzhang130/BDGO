# ADR 0001: LLM provider selection — MiniMax primary, DeepSeek/Claude staged

- **Status**: Accepted
- **Date**: 2026-04-24 (retrospective — decision made during initial scaffolding ~2026-03)

## Context

- App is deployed on a mainland-China VM and serves users inside China; `api.anthropic.com` and most Western LLM endpoints are unreachable from that network.
- Chat requests use Anthropic-compatible tool-use (content blocks, tool_use / tool_result turn structure, SSE streaming).
- We need multi-key concurrency to avoid hitting per-key rate limits during bursts (see `llm_pool.py`).

## Decision

MiniMax is the primary provider. `llm_pool.py` routes every chat request through the MiniMax Anthropic-compat endpoint (`api.minimaxi.com/anthropic/v1/messages`) using a pool of API keys drained with sequential key rotation. DeepSeek and Claude are wired as `ModelSpec` placeholders in `models.py` but gated on env-var presence (`DEEPSEEK_API_KEY` / `CLAUDE_API_KEY`) and not used in prod.

## Consequences

- **Good**: Single-provider config, keeps the hot path simple. MiniMax's Anthropic-compat API means our tool-use / streaming code is portable if we ever move off.
- **Good**: The `ModelSpec` registry lets us A/B-test new models in dev without touching callers.
- **Bad**: We're exposed to MiniMax-specific quirks (e.g. idiosyncratic retry semantics, occasional model-version drift). `OVERLOAD_MSG` handling is MiniMax-specific.
- **Bad**: No true fallback in prod — if MiniMax is down, the whole chat surface is down. DeepSeek/Claude are declared but dormant.

## Alternatives considered

- **OpenAI-compat protocol across the board**: rejected — tool-use conventions differ meaningfully and would force a translation layer.
- **Self-host (vLLM + open-weight model)**: rejected at current scale — ops overhead outweighs the MiniMax bill.
- **True multi-provider round-robin from day one**: deferred. Would need response normalization across providers (different streaming event names, different safety-block formats). Revisit when MiniMax outage pain exceeds integration cost.
