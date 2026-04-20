"""Minimal SSE framing helpers — keeps the streaming modules free of
``f"data: {json.dumps(...)}\\n\\n"`` noise.
"""

from __future__ import annotations

import json
from typing import Any


def sse(event_type: str, **data: Any) -> str:
    """Encode one SSE ``data:`` frame with a ``type`` discriminator."""
    payload = {"type": event_type, **data}
    return "data: " + json.dumps(payload, ensure_ascii=False, default=str) + "\n\n"


def sse_raw(payload: dict) -> str:
    """Encode a pre-built payload (already contains ``type``)."""
    return "data: " + json.dumps(payload, ensure_ascii=False, default=str) + "\n\n"


def sse_done() -> str:
    return sse("done")
