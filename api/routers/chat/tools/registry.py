"""Central tool-dispatch gate: enforces field visibility and count_by guard
before any CRM data reaches the LLM.

Metadata dicts below are intentionally empty at module load time.
``tools/__init__.py`` auto-discovers every sibling module and merges in
each module's TABLE_MAP / NEEDS_USER_ID / MULTI_TABLE_MAP declarations,
so adding a new tool file never requires touching this file.
"""

from __future__ import annotations

import json
import logging

from field_policy import HIDDEN_FIELDS, strip_hidden

logger = logging.getLogger(__name__)

# Sentinel key injected into tool error responses so the streaming loop can
# detect persistent failures without parsing error text.
TOOL_FAILED_KEY = "_tool_failed"

# ── Populated by __init__.py at import time ────────────────────────────────

# Maps tool name → CRM table name for single-table field-visibility stripping.
# e.g. {"search_companies": "公司", "get_asset": "资产"}
TOOL_TABLE: dict[str, str] = {}

# Tool names that require the calling user's ID injected as ``_user_id``.
# e.g. {"add_to_watchlist", "generate_buyer_profile"}
NEEDS_USER_ID: set[str] = set()

# For tools that return a dict of {key: [rows]} spanning multiple CRM tables.
# Maps tool name → list of (result_key, crm_table) pairs to strip in-place.
# e.g. {"search_global": [("companies","公司"), ("assets","资产"), ...]}
MULTI_TABLE_MAP: dict[str, list[tuple[str, str]]] = {}

# ──────────────────────────────────────────────────────────────────────────


def _strip_tool_result(name: str, result, can_see_internal: bool):
    """Apply field_policy to a tool's return value. External users only.

    Single-table tools are handled via TOOL_TABLE.
    Multi-table tools (e.g. search_global) are handled via MULTI_TABLE_MAP.
    Both dicts are populated by __init__.py from each module's declarations.
    """
    if can_see_internal or result is None:
        return result

    table = TOOL_TABLE.get(name)
    if table:
        if isinstance(result, dict) and "error" in result:
            return result
        return strip_hidden(result, table, False)

    pairs = MULTI_TABLE_MAP.get(name)
    if pairs and isinstance(result, dict):
        for key, tbl in pairs:
            if result.get(key):
                result[key] = strip_hidden(result[key], tbl, False)
        return result

    return result


def execute_tool(
    impls: dict,
    name: str,
    inp: dict,
    user_id: str | None = None,
    can_see_internal: bool = False,
) -> str:
    """Dispatch by tool name; return JSON-serialized result (truncated).

    ``can_see_internal`` = True for admins and internal-flagged users.
    When False, hidden CRM fields (BD priority, Q scores, strategic
    analysis, internal notes, etc.) are stripped from the returned rows
    before the LLM ever sees them — matches the REST-side field_policy
    enforcement.
    """
    fn = impls.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})

    # Block count_by on hidden columns for external users — otherwise
    # they could extract the distribution of internal fields (e.g.
    # BD-priority counts). count_by is the only aggregation tool that
    # accepts raw column names, so this guard lives here rather than in
    # the module.
    if name == "count_by" and not can_see_internal:
        table = (inp or {}).get("table", "")
        group_by = (inp or {}).get("group_by", "")
        if group_by in HIDDEN_FIELDS.get(table, set()):
            return json.dumps(
                {"error": f"字段 '{group_by}' 不对外部用户开放"},
                ensure_ascii=False,
            )

    try:
        kwargs = dict(inp or {})
        # Inject caller's user_id for tools that need it (e.g. watchlist,
        # report generators). The set is populated from each module's
        # NEEDS_USER_ID declaration by __init__.py.
        if user_id and name in NEEDS_USER_ID:
            kwargs["_user_id"] = user_id

        result = fn(**kwargs)

        # Enforce three-tier field visibility before handing data to the LLM.
        result = _strip_tool_result(name, result, can_see_internal)

        s = json.dumps(result, ensure_ascii=False, default=str)
        if len(s) > 8000:
            s = s[:8000] + "\n...[truncated]"
        return s
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(e), TOOL_FAILED_KEY: True})
