"""
Plan Templates REST endpoints (X-18).

GET  /api/plan-templates          — list all built-in + user-saved templates
GET  /api/plan-templates/{id}     — get a single template (built-in or user-saved)
POST /api/plan-templates          — save a plan as a named template
DELETE /api/plan-templates/{id}   — delete a user-saved template
"""

from __future__ import annotations

import logging

import plan_templates as pt_mod
from auth import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plan-templates", tags=["plan-templates"])


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────


class SaveTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    plan: dict = Field(
        ...,
        description=(
            "Plan object with keys: title, summary, steps. "
            "Typically the plan emitted by the planner phase."
        ),
    )


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    plan: dict
    builtin: bool
    created_at: str | None = None


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("")
async def list_templates(user: dict = Depends(get_current_user)):
    """Return all built-in templates plus the user's saved templates.

    Built-ins always come first, sorted by their canonical order.
    User-saved templates follow, newest-first.
    """
    builtins = pt_mod.list_builtins()
    user_id = user["id"]
    try:
        user_saved = pt_mod.list_user_templates(user_id)
    except Exception:
        logger.exception("Failed to load user plan templates for user=%s", user_id)
        user_saved = []

    # Normalise the built-in shape to match saved-template shape for the UI
    builtin_items = [
        {
            "id": t["slug"],
            "name": t["title"],
            "description": t.get("description", ""),
            "plan": {
                "plan_id": t["plan_id"],
                "title": t["title"],
                "summary": t["summary"],
                "steps": t["steps"],
            },
            "builtin": True,
            "created_at": None,
        }
        for t in builtins
    ]

    return {"builtin": builtin_items, "saved": user_saved}


@router.get("/{template_id}")
async def get_template(template_id: str, user: dict = Depends(get_current_user)):
    """Get a single template by ID (built-in slug or user-saved UUID)."""
    user_id = user["id"]

    builtin = pt_mod.get_builtin(template_id)
    if builtin:
        return {
            "id": builtin["slug"],
            "name": builtin["title"],
            "description": builtin.get("description", ""),
            "plan": {
                "plan_id": builtin["plan_id"],
                "title": builtin["title"],
                "summary": builtin["summary"],
                "steps": builtin["steps"],
            },
            "builtin": True,
            "created_at": None,
        }

    try:
        saved = pt_mod.get_user_template(user_id, template_id)
    except Exception as exc:
        logger.exception("Failed to fetch template %s for user=%s", template_id, user_id)
        raise HTTPException(status_code=500, detail="Failed to load template") from exc

    if not saved:
        raise HTTPException(status_code=404, detail="Template not found")

    return saved


@router.post("", status_code=201)
async def save_template(
    body: SaveTemplateRequest,
    user: dict = Depends(get_current_user),
):
    """Save a plan as a named template. Returns the new template ID."""
    user_id = user["id"]

    # Minimal validation: plan must have steps
    steps = body.plan.get("steps") or []
    if not steps:
        raise HTTPException(
            status_code=422,
            detail="plan.steps must be a non-empty list",
        )
    if len(steps) > 10:
        raise HTTPException(
            status_code=422,
            detail="plan.steps exceeds maximum of 10 steps",
        )

    try:
        new_id = pt_mod.save_template(
            user_id=user_id,
            name=body.name,
            description=body.description,
            plan=body.plan,
        )
    except Exception as exc:
        logger.exception("Failed to save plan template for user=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to save template") from exc

    return {"id": new_id, "name": body.name}


@router.delete("/{template_id}", status_code=200)
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    """Delete a user-saved template. Built-in templates cannot be deleted."""
    # Guard: built-ins cannot be deleted
    if pt_mod.get_builtin(template_id):
        raise HTTPException(status_code=403, detail="Built-in templates cannot be deleted")

    user_id = user["id"]
    try:
        deleted = pt_mod.delete_user_template(user_id, template_id)
    except Exception as exc:
        logger.exception("Failed to delete template %s for user=%s", template_id, user_id)
        raise HTTPException(status_code=500, detail="Failed to delete template") from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"deleted": True, "id": template_id}
