"""Conference data access — shared by the conference router and the
chat tools that surface conference data to the assistant.

Pre-processed per-session JSON (company flash cards + abstract details)
lives in ``CONFERENCES_DIR / <session_id> / report_data.json``. This
module owns the read path; routers layer HTTP concerns (404s, filters,
pagination) on top.
"""

from __future__ import annotations

import json
from functools import lru_cache

from config import CONFERENCES_DIR


@lru_cache(maxsize=8)
def load_report_data(session_id: str) -> dict:
    """Load and cache ``report_data.json`` for a session.

    Raises ``FileNotFoundError`` if the session has no report_data.json
    yet — callers decide how to surface that (HTTPException, empty
    result, etc.).
    """
    path = CONFERENCES_DIR / session_id / "report_data.json"
    if not path.exists():
        raise FileNotFoundError(f"report_data.json not found for {session_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
