"""Plan-mode trigger heuristic.

Deciding whether an auto-mode request warrants the planner phase.
The planner LLM itself lives in ``api/planner.py``; this module only
contains the cheap keyword/length heuristic.

Design goals (P2-09 — deeper planner):
  - Cover bilingual / English-first queries (many BD users type in English)
  - Cover explicit BD workflow intents (intake, deep-dive, full analysis)
  - Avoid false positives on simple questions (one-liner lookups)
  - Never call the planner LLM — this is a zero-cost gate, not a model call
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────
# Chinese BD planning keywords
# ─────────────────────────────────────────────────────────────
# Phrases that indicate the user wants a multi-step analysis,
# not a quick lookup.

_CN_PLAN_KEYWORDS = (
    # Depth / breadth signals
    "分析",
    "深度",
    "深入",
    "全面",
    "综合",
    "系统",
    "完整",
    # BD workflow terms
    "画像",
    "资产评估",
    "买方匹配",
    "接触时机",
    "策略",
    "BD机会",
    "BD 机会",
    "机会分析",
    "BD策略",
    "BD 策略",
    "竞争格局",
    "市场调研",
    "管线分析",
    "pipeline分析",
    # Report-intent signals
    "报告",
    "梳理",
    "盘点",
    "整理",
    "汇总",
    "规划",
    # Comparison / screening signals
    "对比",
    "筛选",
    "找出",
    "评估",
    "比较",
    "排名",
    # Intake / lifecycle signals
    "intake",
    "全套",
    "全流程",
    "详细了解",
    "全面了解",
    "scout",
)

# ─────────────────────────────────────────────────────────────
# English BD planning keywords  (P2-09 addition)
# ─────────────────────────────────────────────────────────────
# Lower-cased for case-insensitive matching.

_EN_PLAN_KEYWORDS_LOWER = (
    # Depth signals
    "deep dive",
    "deep-dive",
    "in-depth",
    "comprehensive",
    "full analysis",
    "detailed analysis",
    "thorough",
    "end-to-end",
    "end to end",
    # BD workflow intents
    "bd intake",
    "bd analysis",
    "bd strategy",
    "deal analysis",
    "deal evaluation",
    "asset evaluation",
    "buyer analysis",
    "buyer profile",
    "buyer landscape",
    "competitive landscape",
    "competitive analysis",
    "market landscape",
    "pipeline analysis",
    "pipeline gap",
    "ip analysis",
    "ip landscape",
    "fto analysis",
    "outreach strategy",
    "outreach campaign",
    "target analysis",
    "target landscape",
    "disease landscape",
    # Report-intent signals
    "generate a report",
    "create a report",
    "write a report",
    "prepare a report",
    "full report",
    "summary report",
    # Comparison / screening
    "compare",
    "rank",
    "shortlist",
    "screen",
    "evaluate",
    "assess",
    # Lifecycle signals
    "full intake",
    "run an intake",
    "run a full",
    "full bd",
    "due diligence",
    "dd prep",
    "data room",
    "deal teaser",
    # Multi-step workflow phrases
    "step by step",
    "step-by-step",
    "break it down",
    "walk me through",
    "help me plan",
    "prepare me for",
    "prepare for meeting",
    "pre-meeting",
)

# ─────────────────────────────────────────────────────────────
# Explicit multi-step BD patterns (case-insensitive, English)
# These phrases almost always require a multi-step plan.
# ─────────────────────────────────────────────────────────────

_EN_STRONG_PATTERNS_LOWER = (
    "top buyer",
    "top-buyer",
    "find buyer",
    "identify buyer",
    "buyer match",
    "who should we approach",
    "who should i approach",
    "best time to reach",
    "best time to approach",
    "when to reach",
    "outreach timing",
    "best time to contact",
    "how should we position",
    "how should i position",
    "swot",
    "rnpv",
    "r-npv",
    "valuation model",
    "deal memo",
    "bd memo",
    "strategy memo",
)


def should_plan(message: str) -> bool:
    """Heuristic: decide if an auto-mode request warrants a plan phase.

    Used when ``plan_mode == "auto"``. ``plan_mode == "on"`` always plans;
    ``plan_mode == "off"`` never plans — this function is only consulted
    in between.

    Returns True if the message contains planning signals:
      1. Long message (>150 chars) — likely complex
      2. Chinese planning keyword present
      3. English planning keyword present (case-insensitive)
      4. Strong English BD pattern present (case-insensitive)
    """
    if not message or len(message.strip()) < 8:
        return False

    # Long messages almost always imply a complex, multi-step request
    if len(message) > 150:
        return True

    # Chinese keywords (fast path — most production queries are Chinese-first)
    if any(kw in message for kw in _CN_PLAN_KEYWORDS):
        return True

    # English keywords (case-insensitive) — covers bilingual + English-only queries
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in _EN_PLAN_KEYWORDS_LOWER):
        return True

    # Strong BD-specific English patterns (also case-insensitive)
    return any(pat in msg_lower for pat in _EN_STRONG_PATTERNS_LOWER)
