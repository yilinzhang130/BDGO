"""Schema validator tests for company_analysis mode (8-section company report)."""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_COMPANY = """# Peg-Bio 公司分析 (买方视角)

## 一、一页摘要
Peg-Bio 是 Phase 2 ADC biotech，主打 KRAS G12C，团队来自 J&J，cash runway 18 months。

## 二、公司基本面
- 成立时间：2020 年
- 总部：上海
- 市值：$1.2B（2026Q1 预 IPO 估值）
- 雇员：120 人（R&D 80）
- 主营：肿瘤精准治疗 ADC 平台

## 三、管线 / 核心资产
| 资产名称 | 靶点 | 阶段 | 适应症 | 差异化分级 |
|---|---|---|---|---|
| PEG-001 | KRAS G12C | Phase 2 | NSCLC | BIC |
| PEG-002 | HER2 | Phase 1 | breast | FIC |

## 四、BD 历史
| 日期 | 对手方 | 类型 | 资产 | 公开金额 |
|---|---|---|---|---|
| 2024-09 | Eli Lilly | option | PEG-001 (China) | $20M upfront |
| 2025-03 | Merck | partnership | discovery | undisclosed |

## 五、团队
- **CEO**: Dr. Wang Jian, 前 J&J VP Oncology
- **CSO**: Dr. Liu Mei, 前 Genentech Director
- **Head of BD**: Sarah Chen, 前 Roche BD VP

## 六、战略缺口 / 优先级
公司管线集中肿瘤但缺免疫学领域；BD 优先级是补 immunology pipeline gap。

## 七、风险提示
1. **CMC scale-up 风险** — Phase 3 商业批次未验证 (L2 推断)
2. **竞品 P3 readout 时间窗口** — Mirati 同靶点 2026Q4 readout (L4 外部)

## 八、建议下一步
- 持续追踪 PEG-001 的 P2 readout（预计 2026Q3）
- 评估 Merck partnership 的 progress
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_COMPANY, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_missing_one_page_summary_fails():
    md = WELL_FORMED_COMPANY.replace("## 一、一页摘要\n", "## 概述\n")
    audit = validate_markdown(md, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "one_page_summary" for f in fails)


def test_validator_missing_fundamentals_signal_fails():
    """Fundamentals section without 成立/总部/市值/雇员 keywords fails."""
    md = WELL_FORMED_COMPANY.replace(
        "- 成立时间：2020 年\n- 总部：上海\n- 市值：$1.2B（2026Q1 预 IPO 估值）\n- 雇员：120 人（R&D 80）\n",
        "- 描述：肿瘤精准治疗\n",
    )
    audit = validate_markdown(md, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "company_fundamentals" for f in fails)


def test_validator_missing_bd_history_evidence_fails():
    """BD history section without any deal evidence or 'no deals' marker fails."""
    md = WELL_FORMED_COMPANY.replace(
        "## 四、BD 历史\n"
        "| 日期 | 对手方 | 类型 | 资产 | 公开金额 |\n"
        "|---|---|---|---|---|\n"
        "| 2024-09 | Eli Lilly | option | PEG-001 (China) | $20M upfront |\n"
        "| 2025-03 | Merck | partnership | discovery | undisclosed |\n",
        "## 四、BD 历史\n仅做内部研发，未公开任何动作。\n",
    )
    audit = validate_markdown(md, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "bd_history" for f in fails)


def test_validator_team_without_leadership_role_fails():
    """Team section needs at least 1 leadership role (CEO/CSO/CMO/CFO/...)."""
    md = WELL_FORMED_COMPANY.replace(
        "- **CEO**: Dr. Wang Jian, 前 J&J VP Oncology\n"
        "- **CSO**: Dr. Liu Mei, 前 Genentech Director\n"
        "- **Head of BD**: Sarah Chen, 前 Roche BD VP\n",
        "- 一些重要的人\n",
    )
    audit = validate_markdown(md, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "team" for f in fails)


def test_validator_only_one_risk_fails():
    """Risk section needs ≥2 numbered items."""
    md = WELL_FORMED_COMPANY.replace(
        "1. **CMC scale-up 风险** — Phase 3 商业批次未验证 (L2 推断)\n"
        "2. **竞品 P3 readout 时间窗口** — Mirati 同靶点 2026Q4 readout (L4 外部)\n",
        "1. **CMC scale-up 风险** — Phase 3 商业批次未验证 (L2 推断)\n",
    )
    audit = validate_markdown(md, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "risk_callouts" for f in fails)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_COMPANY.replace(
        "Peg-Bio 是 Phase 2 ADC biotech",
        "Peg-Bio 是行业领先的 Phase 2 ADC biotech，巨大潜力",
    )
    audit = validate_markdown(md, mode="company_analysis")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_eight_sections_all_required():
    """Drop multiple sections → multiple section_missing fails."""
    md = WELL_FORMED_COMPANY
    md = md.replace("## 五、团队\n", "## XYZZY1\n")
    md = md.replace("## 六、战略缺口 / 优先级\n", "## XYZZY2\n")
    md = md.replace("## 八、建议下一步\n", "## XYZZY3\n")
    audit = validate_markdown(md, mode="company_analysis")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"team", "strategic_gap", "next_steps"} <= fail_sections
