"""Unit tests for should_plan() heuristic (P2-09 — deeper planner).

Coverage:
  1. Short / empty messages → False
  2. Long message (>150 chars) → True
  3. Chinese keywords → True
  4. English keywords (case-insensitive) → True
  5. English strong BD patterns → True
  6. Simple quick-lookup queries → False (no false positives)
  7. Mixed Chinese/English queries → True
"""

from __future__ import annotations

import pytest
from routers.chat.planning import should_plan

# ─────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────


def test_empty_string_is_false():
    assert should_plan("") is False


def test_none_like_whitespace_is_false():
    assert should_plan("   ") is False


def test_very_short_message_is_false():
    assert should_plan("Hi") is False
    assert should_plan("ok") is False


# ─────────────────────────────────────────────────────────────
# Length trigger
# ─────────────────────────────────────────────────────────────


def test_long_message_triggers():
    msg = "a" * 151
    assert should_plan(msg) is True


def test_150_chars_does_not_trigger_by_length_alone():
    """Exactly 150 chars: length alone not sufficient — needs keywords too.
    (The threshold is > 150, i.e. 151+.)
    """
    msg = "x" * 150  # no keywords
    assert should_plan(msg) is False


# ─────────────────────────────────────────────────────────────
# Chinese keywords
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "message",
    [
        "帮我分析 Pfizer 的管线",
        "深度了解 BeiGene 的 BD 策略",
        "生成一份 MNC 买方画像报告",
        "找出适合 KRAS G12D 资产的买方",
        "筛选最近有 oncology in-license 记录的公司",
        "对比 Roche 和 Novartis 的 BD 偏好",
        "评估这个资产的吸引力",
        "梳理一下 AstraZeneca 的管线空缺",
        "盘点 2024 年 NSCLC 领域的重大交易",
        "给我一个全面的竞争格局分析",
        "生成 BD 策略备忘",
        "这个资产的评估报告怎么写",
        "全套 BD intake 分析",
        "帮我规划接触时机策略",
    ],
)
def test_chinese_keywords_trigger(message):
    assert should_plan(message) is True, f"Expected True for: {message!r}"


# ─────────────────────────────────────────────────────────────
# English keywords (P2-09 additions)
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "message",
    [
        "Do a deep dive on Pfizer's oncology pipeline",
        "Comprehensive analysis of KRAS inhibitors",
        "Full analysis of AstraZeneca's BD strategy",
        "Run a full BD intake for this asset",
        "Prepare a competitive landscape for PD-1 antibodies",
        "I need a buyer profile for Roche",
        "Help me with due diligence prep",
        "Generate a deal evaluation report",
        "Create a report on BeiGene's recent deals",
        "Run an outreach campaign for Top-5 buyers",
        "step by step plan for reaching out to MNCs",
        "Prepare for meeting with Lilly",
        "Walk me through a full BD strategy",
        "Find top buyers for KRAS G12D inhibitor",
        "What is the best time to approach Pfizer",
        "Help me build a BD memo for this asset",
        "Do an RNPV valuation model",
        "Assess the asset's attractiveness",
        "Compare Roche and Novartis deal preferences",
    ],
)
def test_english_keywords_trigger(message):
    assert should_plan(message) is True, f"Expected True for: {message!r}"


def test_english_keywords_case_insensitive():
    """Keywords must match regardless of casing."""
    assert should_plan("DEEP DIVE into Pfizer") is True
    assert should_plan("Comprehensive Analysis Required") is True
    assert should_plan("BD INTAKE for new asset") is True


# ─────────────────────────────────────────────────────────────
# Mixed Chinese / English (common in practice)
# ─────────────────────────────────────────────────────────────


def test_mixed_chinese_english_triggers():
    assert should_plan("帮我对 Roche 做一个 deep dive") is True
    assert should_plan("请分析 AstraZeneca 的 pipeline gap") is True
    assert should_plan("做一个 comprehensive BD strategy") is True


# ─────────────────────────────────────────────────────────────
# False-positive guard: simple lookups should NOT trigger
# ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "message",
    [
        "What is BeiGene's ticker?",
        "查一下 Amgen 的公司名称",
        "帮我找 Zymeworks 的邮箱",
        "What phase is NCT12345?",
        "/teaser company_name=Foo asset_name=Bar",
        "公司总部在哪里",
        "搜索 Roche",
        "hello",
        "谢谢",
        "好的",
    ],
)
def test_simple_queries_do_not_trigger(message):
    assert should_plan(message) is False, f"Expected False for: {message!r}"


# ─────────────────────────────────────────────────────────────
# Strong BD patterns
# ─────────────────────────────────────────────────────────────


def test_strong_bd_patterns_trigger():
    assert should_plan("who should we approach for an out-license deal") is True
    assert should_plan("when is the best time to reach out to Lilly") is True
    assert should_plan("run a SWOT analysis on this asset") is True
    assert should_plan("build a valuation model for this drug") is True
    assert should_plan("create a strategy memo for the partnership") is True
