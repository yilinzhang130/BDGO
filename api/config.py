"""
Shared configuration constants.

Keep secrets/endpoints/paths in one place so rotation is a single-file change.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException

# ─────────────────────────────────────────────────────────────
# LLM endpoints
# ─────────────────────────────────────────────────────────────

MINIMAX_URL = os.environ.get(
    "MINIMAX_URL",
    "https://api.minimaxi.com/anthropic/v1/messages",
)
MINIMAX_KEY = os.environ.get(
    "MINIMAX_API_KEY",
    "sk-cp-ZCX3QqqgveWIUJdbn8u6N-SMTWJfKBr-BuUVaaO5jxlH5c6ArI24AfBPXqQqu-HmbUxXis9OLBf9EOyuBV8URHNVSQFmzcAfkI4zrTA8VTDa36M_m4900aQ",
)
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M1-80k")
MINIMAX_ANTHROPIC_VERSION = "2023-06-01"

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

BP_DIR = Path(os.path.expanduser("~/.openclaw/workspace/BP"))
REPORTS_DIR = Path(os.path.expanduser("~/.openclaw/workspace/Reports"))


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

def safe_path_within(base: Path, filename: str) -> Path:
    """Resolve filename strictly inside base dir, rejecting path traversal.

    Raises HTTPException(400) on any attempt to escape base.
    """
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    resolved = (base / safe_name).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return resolved
