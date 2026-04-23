"""Credits router — balance, usage history, model list, admin top-up."""

import credits as credits_mod
from auth import get_current_user, require_admin_header
from fastapi import APIRouter, Depends, Header, HTTPException
from models import available_models
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["credits"])


@router.get("/credits/balance")
def get_balance(user: dict = Depends(get_current_user)):
    return credits_mod.get_balance(user["id"])


@router.get("/credits/usage")
def get_usage(limit: int = 50, user: dict = Depends(get_current_user)):
    return {"items": credits_mod.list_usage(user["id"], limit=limit)}


@router.get("/models")
def list_models(user: dict = Depends(get_current_user)):
    """Available LLM models for the model picker."""
    return {"models": available_models()}


# ─────────────────────────────────────────────────────────────
# Admin top-up
# ─────────────────────────────────────────────────────────────


class GrantBody(BaseModel):
    user_id: str
    amount: float
    reason: str = ""


@router.post("/admin/credits/grant")
def admin_grant(body: GrantBody, x_admin_key: str = Header(...)):
    require_admin_header(x_admin_key)
    if body.amount <= 0:
        raise HTTPException(400, "amount 必须大于 0")
    return credits_mod.grant_credits(body.user_id, body.amount, body.reason)
