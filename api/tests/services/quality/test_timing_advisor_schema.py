"""Schema validator tests for timing_advisor mode (5-section timing report)."""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_TIMING = """# Eli Lilly — PEG-001 接触时机建议

> **生成日期**: 2026-04-26  ·  **视角**: seller

## 一、推荐窗口

- **窗口**：2026-09-01 至 2026-10-15（约 6 周）
- **理由**：在 Mirati 同靶点 P3 readout 前完成 cold outreach
- **建议动作**：cold outreach + partnering meeting request
- **预期 leverage**：高 — 买方未被竞品 readout 分散注意力

## 二、避开窗口

- 2026-12-01 至 2026-12-15：ASH 大会期间，对方 BD 团队全员现场
- 2026-08-15 至 2026-08-30：财报前 IR 锁定期，公开沟通受限

## 三、催化剂时间表

| 日期 | 事件 | 类型 | 确定性 | BD 含义 |
|---|---|---|---|---|
| 2026-09-15 | PEG-001 P2 readout | Readout | High | leverage 上升或下降，看数据 |
| 2026-11-01 | IND amendment | Filing | High | hint at expansion plan |

## 四、会议时间表

| 日期 | 会议简称 | 类型 | 是否建议接触 |
|---|---|---|---|
| 2026-06-02 | ASCO | scientific | yes — 提前预约会议 |
| 2026-09-19 | ESMO | scientific | yes — 数据后接触 |
| 2027-01-12 | JPM HC | deal-making | yes — 关键 deal-making 窗口 |

## 五、整体策略一句话

P2 readout 前 6 周接触 Eli Lilly。
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_TIMING, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_missing_recommended_windows_fails():
    md = WELL_FORMED_TIMING.replace("## 一、推荐窗口\n", "## 概览\n")
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "recommended_windows" for f in fails)


def test_validator_recommended_windows_without_dates_fails():
    """Recommended windows must have YYYY-MM-DD format."""
    md = WELL_FORMED_TIMING.replace(
        "- **窗口**：2026-09-01 至 2026-10-15（约 6 周）",
        "- **窗口**：今年第三季度（约 6 周）",
    )
    # Also strip the date that appears in the catalyst table to avoid bleed
    # — but actually the section detection is per-section, so the catalyst
    # table dates won't satisfy recommended_windows
    md = md.replace("2026-09-15", "Q3 2026").replace("2026-11-01", "Q4 2026")
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "recommended_windows" for f in fails)


def test_validator_avoid_windows_without_keyword_fails():
    md = WELL_FORMED_TIMING.replace(
        "## 二、避开窗口\n\n"
        "- 2026-12-01 至 2026-12-15：ASH 大会期间，对方 BD 团队全员现场\n"
        "- 2026-08-15 至 2026-08-30：财报前 IR 锁定期，公开沟通受限\n",
        "## 二、避开窗口\n\n仅在工作日发邮件即可。\n",
    )
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "avoid_windows" for f in fails)


def test_validator_catalyst_timeline_without_event_kw_fails():
    """Catalyst table must mention at least one catalyst keyword."""
    md = WELL_FORMED_TIMING.replace(
        "| 2026-09-15 | PEG-001 P2 readout | Readout | High | leverage 上升或下降，看数据 |\n"
        "| 2026-11-01 | IND amendment | Filing | High | hint at expansion plan |\n",
        "| 2026-09-15 | 内部活动 | Other | High | 内部 |\n",
    )
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "catalyst_timeline" for f in fails)


def test_validator_conference_timeline_without_known_meeting_fails():
    """Conference table must mention at least one known BD conference."""
    md = WELL_FORMED_TIMING.replace(
        "| 2026-06-02 | ASCO | scientific | yes — 提前预约会议 |\n"
        "| 2026-09-19 | ESMO | scientific | yes — 数据后接触 |\n"
        "| 2027-01-12 | JPM HC | deal-making | yes — 关键 deal-making 窗口 |\n",
        "| 2026-06-02 | UnknownConf | other | maybe |\n",
    )
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "conference_timeline" for f in fails)


def test_validator_missing_overall_strategy_fails():
    md = WELL_FORMED_TIMING.replace(
        "## 五、整体策略一句话\n\nP2 readout 前 6 周接触 Eli Lilly。\n",
        "",
    )
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "overall_strategy" for f in fails)


def test_validator_vague_advice_warns():
    """'建议尽快联系' triggers a vague_advice warn — explicitly forbidden by prompt."""
    md = WELL_FORMED_TIMING.replace(
        "P2 readout 前 6 周接触 Eli Lilly。",
        "建议尽快联系 Eli Lilly。",
    )
    audit = validate_markdown(md, mode="timing_advisor")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("vague_advice" in (f.section or "") for f in warns)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_TIMING.replace(
        "## 五、整体策略一句话\n\nP2 readout 前 6 周接触 Eli Lilly。\n",
        "## 五、整体策略一句话\n\nindustry-leading 时机。\n",
    )
    audit = validate_markdown(md, mode="timing_advisor")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_five_sections_all_required():
    """Drop multiple sections → multiple fails."""
    md = WELL_FORMED_TIMING
    md = md.replace("## 三、催化剂时间表\n", "## XYZZY1\n")
    md = md.replace("## 四、会议时间表\n", "## XYZZY2\n")
    audit = validate_markdown(md, mode="timing_advisor")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"catalyst_timeline", "conference_timeline"} <= fail_sections
