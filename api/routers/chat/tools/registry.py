"""Central tool-dispatch gate.

``execute_tool`` is called from the streaming loop for every tool_use
block the LLM emits. It:

  1. Looks up the impl from the assembled ``IMPL`` dict (see ``__init__.py``)
  2. Rejects ``count_by`` on hidden columns for external users
  3. Invokes the impl, injecting ``_user_id`` where needed
  4. Applies field-visibility stripping to CRM results
  5. Returns a truncated JSON string

Field visibility is enforced here, NOT in individual tool impls — so
every CRM data path gets consistent treatment regardless of which tool
the LLM picked.
"""

from __future__ import annotations

import json
import logging

from field_policy import HIDDEN_FIELDS, strip_hidden

logger = logging.getLogger(__name__)


# Map each CRM tool to its source table so we can apply field visibility.
# Tools NOT in this map (watchlist / reports / skill calls) are not filtered.
TOOL_TABLE: dict[str, str] = {
    "search_companies": "公司",
    "get_company": "公司",
    "search_assets": "资产",
    "get_asset": "资产",
    "search_clinical": "临床",
    "search_deals": "交易",
}


def _strip_tool_result(name: str, result, can_see_internal: bool):
    """Apply field_policy to a tool's return value. External users only.

    Handles the 6 individual CRM tools plus search_global (which returns
    a dict of {companies, assets, deals, clinical} sub-lists).
    """
    if can_see_internal or result is None:
        return result

    table = TOOL_TABLE.get(name)
    if table:
        # strip_hidden handles both dict (single row) and list[dict]
        if isinstance(result, dict) and "error" in result:
            return result
        return strip_hidden(result, table, False)

    if name == "search_global" and isinstance(result, dict):
        pairs = (
            ("companies", "公司"), ("assets", "资产"),
            ("deals", "交易"), ("clinical", "临床"),
        )
        for key, tbl in pairs:
            if key in result and result[key]:
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
    # BD-priority counts).
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
        if user_id and name == "add_to_watchlist":
            kwargs["_user_id"] = user_id
        elif user_id and name.startswith("generate_"):
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
        return json.dumps({"error": str(e)})
