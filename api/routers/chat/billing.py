"""Credits billing helpers for chat + planner turns.

All error paths in stream_chat ``return`` before reaching the billing
helpers, so a failed turn is never charged. Admin users always skip.
"""

from __future__ import annotations

import asyncio
import logging

import credits as credits_mod
from models import ModelSpec

logger = logging.getLogger(__name__)


async def charge_turn(
    *,
    user_id: int | None,
    session_id: str,
    model: ModelSpec,
    usage_accum: dict,
    is_admin: bool,
) -> tuple[float, float | None]:
    """Record tokens and fetch the updated balance.

    Returns ``(credits_charged, balance_remaining)``. Admins and
    anonymous users are never billed — both values come back as ``0.0``
    / ``None`` in that case.
    """
    if not user_id or is_admin:
        return 0.0, None

    credits_charged = await asyncio.to_thread(
        credits_mod.record_usage,
        user_id=user_id,
        session_id=session_id,
        model_id=model.id,
        input_tokens=usage_accum.get("input_tokens", 0),
        output_tokens=usage_accum.get("output_tokens", 0),
        input_weight=model.input_weight,
        output_weight=model.output_weight,
    )
    try:
        balance_info = await asyncio.to_thread(credits_mod.get_balance, user_id)
        balance_remaining = balance_info["balance"]
    except Exception:
        balance_remaining = None
    return credits_charged, balance_remaining
