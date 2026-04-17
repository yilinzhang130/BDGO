"""Chat streaming endpoint + request/response models.

Entry point into the chat feature. Owns the FastAPI ``router`` object
and decides which phase to run (plan / plan-confirm execution / normal
execution). Delegates everything else to submodules.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import credits as credits_mod
from auth import get_current_user

from .planning import should_plan
from .streaming import stream_chat, stream_plan_only


# ─────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────

class PlanConfirm(BaseModel):
    plan_id: str
    plan_title: str
    selected_steps: list[dict]      # [{id, title, description, tools_expected}]
    original_message: str


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    file_ids: list[str] = []
    model_id: str | None = None   # selected from /api/models; falls back to default
    # Plan mode: "auto" (heuristic), "on" (always plan), "off" (skip planning)
    plan_mode: str = "auto"
    plan_confirm: PlanConfirm | None = None
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
