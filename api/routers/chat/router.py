"""Chat streaming endpoint + request/response models.

Entry point into the chat feature. Owns the FastAPI ``router`` object
and decides which phase to run (plan / plan-confirm execution / normal
execution). Delegates everything else to submodules.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

import credits as credits_mod
from auth import get_current_user

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


@router.post("")
async def chat_stream(req: ChatRequest, user: dict = Depends(get_current_user)):
    req.user_id = user["id"]
    req.is_admin = bool(user.get("is_admin"))
    req.is_internal = bool(user.get("is_internal"))
    # Admin users bypass credit check (still logged, just never blocked).
    if not req.is_admin:
        # Fail fast with a clean 402 if the user is out of credits —
        # never mid-stream.
        credits_mod.ensure_balance(user["id"])

    # Quick-search mode bypasses planning and tool-use entirely.
    if req.search_mode == "quick" and req.plan_confirm is None:
        return StreamingResponse(
            stream_quick_search(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
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
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
