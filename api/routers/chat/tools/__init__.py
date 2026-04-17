"""Assemble the chat tool registry.

Each submodule exports:
  - ``SCHEMAS``: list[dict] — tool definitions passed to the LLM API body
  - ``IMPLS``:   dict[str, Callable] — name → implementation function

This module flattens them into the two module-level constants the
streaming layer hands to the LLM:
  - ``TOOLS``     — concatenation of all schemas
  - ``TOOL_IMPL`` — merge of all impl maps

Adding a new tool module:
  1. Create ``tools/foo.py`` with ``SCHEMAS = [...]`` and ``IMPLS = {...}``
  2. Add it to the ``_MODULES`` tuple below
  No other changes needed anywhere.
"""

from __future__ import annotations

from . import crm, guidelines, reports
from .registry import execute_tool, TOOL_TABLE

_MODULES = (crm, guidelines, reports)

TOOLS: list[dict] = []
TOOL_IMPL: dict = {}

for _mod in _MODULES:
    TOOLS.extend(_mod.SCHEMAS)
    TOOL_IMPL.update(_mod.IMPLS)


__all__ = ["TOOLS", "TOOL_IMPL", "TOOL_TABLE", "execute_tool"]
