"""Assemble the chat tool registry. Each submodule exports ``SCHEMAS``
(LLM-facing tool definitions) and ``IMPLS`` (name → callable); we flatten
them into ``TOOLS`` + ``TOOL_IMPL``."""

from __future__ import annotations

from . import crm, guidelines, reports
from .registry import execute_tool, TOOL_TABLE

_MODULES = (crm, guidelines, reports)

TOOLS: list[dict] = []
TOOL_IMPL: dict = {}

for _mod in _MODULES:
    TOOLS.extend(_mod.SCHEMAS)
    TOOL_IMPL.update(_mod.IMPLS)

REPORT_TOOL_NAME_TO_SLUG: dict[str, str] = dict(reports.TOOL_NAME_TO_SLUG)


__all__ = [
    "TOOLS",
    "TOOL_IMPL",
    "TOOL_TABLE",
    "execute_tool",
    "REPORT_TOOL_NAME_TO_SLUG",
]
