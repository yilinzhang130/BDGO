"""Plan-mode trigger heuristic.

Deciding whether an auto-mode request warrants the planner phase.
The planner LLM itself lives in ``api/planner.py``; this module only
contains the cheap keyword/length heuristic.
"""

from __future__ import annotations

_PLAN_KEYWORDS = (
    "分析", "深度", "画像", "scout", "找出", "筛选",
    "BD机会", "BD 机会", "机会分析", "对比", "评估",
    "深入", "盘点", "梳理", "报告", "全面",
)


def should_plan(message: str) -> bool:
    """Heuristic: decide if an auto-mode request warrants a plan phase.

    Used when ``plan_mode == "auto"``. ``plan_mode == "on"`` always plans;
    ``plan_mode == "off"`` never plans — this function is only consulted
    in between.
    """
    if not message or len(message.strip()) < 8:
        return False
    if len(message) > 150:
        return True
    return any(kw in message for kw in _PLAN_KEYWORDS)
