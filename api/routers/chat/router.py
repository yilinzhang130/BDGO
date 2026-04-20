"""Chat streaming endpoint + request/response models.

Entry point into the chat feature. Owns the FastAPI ``router`` object
and decides which phase to run (plan / plan-confirm execution / normal
execution). Delegates everything else to submodules.
"""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

import credits as credits_mod
from auth import get_current_user
from rate_limit import chat_slot, check_rpm

from .planning import should_plan
from .quick_search import stream_quick_search
from .streaming import stream_chat, stream_plan_only

_STEP_ID_RE = re.compile(r"^s\d+$")


# ─────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────

class PlanStep(BaseModel):
    id: str
    title: str
    description: str = ""
    tools_expected: list[str] = []
    required: bool = False
    default_selected: bool = True
    estimated_seconds: int = 30

    @field_validator("id")
    @classmethod
    def id_must_be_step_id(cls, v: str) -> str:
        if not _STEP_ID_RE.match(v):
            raise ValueError(f"Invalid step id '{v}': must match s<number> (e.g. s1, s2)")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Step title must not be empty")
        return v


class PlanConfirm(BaseModel):
    plan_id: str
    plan_title: str
    selected_steps: list[PlanStep]
    original_message: str

    @field_validator("selected_steps")
    @classmethod
    def steps_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("selected_steps must contain at least one step")
        if len(v) > 10:
            raise ValueError("selected_steps exceeds maximum of 10 steps")
        return v


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    file_ids: list[str] = []
    model_id: str | None = None   # selected from /api/models; falls back to default
    # Plan mode: "auto" (heuristic), "on" (always plan), "off" (skip planning)
    plan_mode: str = "auto"
    plan_confirm: PlanConfirm | None = None
    # Search mode: "agent" (full tool loop) or "quick" (Tavily + summary only)
    search_mode: str = "agent"
    # user_id / is_admin / is_internal are injected by the endpoint,
    # not sent by the client
    user_id: str | None = None
    is_admin: bool = False
    is_internal: bool = False


# ─────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


async def _guarded_stream(gen, user_id: str):
    """Wrap an SSE generator with a concurrent-slot guard.

    The slot is held for the full lifetime of the stream so one user cannot
    exceed MAX_CONCURRENT_CHAT simultaneous open connections. Releasing in a
    ``finally`` block handles normal finish, error, and client-disconnect.
    """
    async with chat_slot(user_id):
        async for chunk in gen:
            yield chunk


@router.post("")
async def chat_stream(req: ChatRequest, user: dict = Depends(get_current_user)):
    req.user_id = user["id"]
    req.is_admin = bool(user.get("is_admin"))
    req.is_internal = bool(user.get("is_internal"))

    # Admins bypass both rate limits and credit checks.
    if not req.is_admin:
        # 1. Sliding-window rate limit: max 20 chat requests / minute.
        await check_rpm(user["id"])

        # 2. Credit check: fail fast with 402 before starting the stream.
        #    Offload to thread — ensure_balance does a psycopg2 query.
        await asyncio.to_thread(credits_mod.ensure_balance, user["id"])

    # Quick-search mode bypasses planning and tool-use entirely.
    if req.search_mode == "quick" and req.plan_confirm is None:
        return StreamingResponse(
            _guarded_stream(stream_quick_search(req), user["id"]),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )

    # Decide: planning phase, execution phase, or normal (no-plan) flow.
    is_confirming = req.plan_confirm is not None
    should_plan_now = (
        not is_confirming
        and req.plan_mode != "off"
        and (req.plan_mode == "on" or should_plan(req.message))
    )

    if should_plan_now:
        generator = stream_plan_only(req)
    else:
        # Normal execution — either no plan mode, or user confirmed a plan.
        # When confirming, use the original message as the chat input so
        # the LLM sees the actual question (not "executed plan confirmation").
        if is_confirming and req.plan_confirm:
            req = req.model_copy(update={"message": req.plan_confirm.original_message})
        generator = stream_chat(req)

    return StreamingResponse(
        _guarded_stream(generator, user["id"]),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
