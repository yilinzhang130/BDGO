"""Auto-discover and assemble the chat tool registry.

Every ``*.py`` file in this package (except ``registry.py``) is treated as
a tool module.  A module may export any of the following:

    SCHEMAS        list[dict]              LLM-facing tool definitions
    IMPLS          dict[str, Callable]     name → implementation
    TABLE_MAP      dict[str, str]          tool → CRM table (field stripping)
    NEEDS_USER_ID  set[str]               tools that receive ``_user_id``
    MULTI_TABLE_MAP dict[str, list]        multi-table field stripping config
    TOOL_NAME_TO_SLUG dict[str, str]       report tool name → slug

To add a new tool group, drop a ``my_tools.py`` file here that exports
``SCHEMAS`` and ``IMPLS`` — no changes to any existing file required.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

from .registry import (
    MULTI_TABLE_MAP,
    NEEDS_USER_ID,
    TOOL_TABLE,
    execute_tool,
)

logger = logging.getLogger(__name__)

TOOLS: list[dict] = []
TOOL_IMPL: dict = {}
REPORT_TOOL_NAME_TO_SLUG: dict[str, str] = {}

_pkg_path = str(Path(__file__).parent)
_pkg_name = __name__  # e.g. "routers.chat.tools"

for _finder, _modname, _ispkg in pkgutil.iter_modules([_pkg_path]):
    if _modname == "registry":
        continue  # registry is infrastructure, not a tool module
    try:
        _mod = importlib.import_module(f"{_pkg_name}.{_modname}")
    except Exception:
        logger.exception("Failed to import tool module '%s' — skipping", _modname)
        continue

    if hasattr(_mod, "SCHEMAS"):
        TOOLS.extend(_mod.SCHEMAS)
    if hasattr(_mod, "IMPLS"):
        TOOL_IMPL.update(_mod.IMPLS)
    if hasattr(_mod, "TABLE_MAP"):
        TOOL_TABLE.update(_mod.TABLE_MAP)
    if hasattr(_mod, "NEEDS_USER_ID"):
        NEEDS_USER_ID.update(_mod.NEEDS_USER_ID)
    if hasattr(_mod, "MULTI_TABLE_MAP"):
        MULTI_TABLE_MAP.update(_mod.MULTI_TABLE_MAP)
    if hasattr(_mod, "TOOL_NAME_TO_SLUG"):
        REPORT_TOOL_NAME_TO_SLUG.update(_mod.TOOL_NAME_TO_SLUG)

logger.debug(
    "Tool registry loaded: %d tools from modules in %s",
    len(TOOLS),
    _pkg_path,
)

__all__ = [
    "TOOLS",
    "TOOL_IMPL",
    "TOOL_TABLE",
    "execute_tool",
    "REPORT_TOOL_NAME_TO_SLUG",
]
