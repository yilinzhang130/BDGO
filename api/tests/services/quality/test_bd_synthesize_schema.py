"""
Schema validator tests for bd_synthesize mode.

Exercises L0 audit against the 7-section BD strategy memo.
"""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_MEMO = """# BD 策略备忘 — Peg-Bio / PEG-001

> **生成日期**: 2026-04-26  ·  **依据**: 5 份调研报告

## 一、资产定位（一句话）
KRAS G12C 抑制剂，Phase 2，FIC 定位，主适应症 NSCLC。

## 二、BD 可能性评分
- 综合评分：⭐⭐⭐⭐ / 5
- /evaluate 报告显示 Stage A 合格 + Path-R 双通道；ORR 38% vs SoC 18%。

## 三、推荐 Deal 结构
- 推荐结构：License 出（ex-China territory）
- 估值锚点：upfront $50-80M / total $800M-1.2B（参考 ADC Phase 2 可比）
- License 而非 acquisition 因为母公司有非肿瘤管线

## 四、Top-3 买方匹配
| Rank | Buyer | 为什么 fit | Outreach 优先级 |
|---|---|---|---|
| 1 | Eli Lilly | 近 24 月 KRAS BD 活跃 | High |
| 2 | Pfizer | 肿瘤 portfolio gap | High |
| 3 | BeiGene | China license-in 通道 | Med |

## 五、关键风险 Top-3
1. **CMC scale-up 不确定** — Phase 3 商业批次未验证 (L2 推断)
2. **专利 PRTC freedom** — EU CoM expiry 2032 (L1 文本)
3. **竞品 P3 readout** — Mirati 同靶点 P3 2026Q4 (L4 外部)

来源：从 /ip / /evaluate / /target 报告提炼。

## 六、推荐时间窗口
- 最优窗口：2026-09-01 至 2026-10-15
- 理由：在 Mirati P3 readout 前完成 cold outreach，避开他们的市场反应期

## 七、下一步 Action
1. 本周内：发 Eli Lilly cold outreach（参考 timing 报告）
2. 2 周内：准备 dataroom 结构 (CMC + IP redacted 版本)
3. P2 readout 前 6 周：开 Pfizer 二轮接触
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_MEMO, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_missing_top_buyers_fails():
    md = WELL_FORMED_MEMO.replace("## 四、Top-3 买方匹配", "## ZZZ removed")
    audit = validate_markdown(md, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "top_buyers" for f in fails)


def test_validator_only_two_buyers_fails():
    """Drop Rank 3 row → must_contain_all fails for the 3rd ranking."""
    md = WELL_FORMED_MEMO.replace("| 3 | BeiGene | China license-in 通道 | Med |\n", "")
    audit = validate_markdown(md, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "top_buyers" for f in fails)


def test_validator_missing_third_risk_fails():
    md = WELL_FORMED_MEMO.replace(
        "3. **竞品 P3 readout** — Mirati 同靶点 P3 2026Q4 (L4 外部)\n", ""
    )
    audit = validate_markdown(md, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "key_risks" for f in fails)


def test_validator_risks_without_source_levels_fails():
    """Risks must include L1/L2/L3/L4 source ladder."""
    md = WELL_FORMED_MEMO.replace("(L2 推断)", "").replace("(L1 文本)", "").replace("(L4 外部)", "")
    audit = validate_markdown(md, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "key_risks" for f in fails)


def test_validator_missing_score_emoji_fails():
    md = WELL_FORMED_MEMO.replace("- 综合评分：⭐⭐⭐⭐ / 5", "- 综合评分：good")
    audit = validate_markdown(md, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "bd_score" for f in fails)


def test_validator_missing_deal_keyword_fails():
    md = WELL_FORMED_MEMO.replace(
        "- 推荐结构：License 出（ex-China territory）", "- 推荐结构：something else"
    ).replace(
        "License 而非 acquisition 因为母公司有非肿瘤管线",
        "something else 而非 something",
    )
    audit = validate_markdown(md, mode="bd_synthesize")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "deal_structure" for f in fails)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_MEMO.replace(
        "KRAS G12C 抑制剂",
        "KRAS G12C 抑制剂，industry-leading 资产",
    )
    audit = validate_markdown(md, mode="bd_synthesize")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_soft_advice_voice_warns():
    md = WELL_FORMED_MEMO.replace(
        "## 七、下一步 Action\n1.",
        "## 七、下一步 Action\n建议您可以：\n1.",
    )
    audit = validate_markdown(md, mode="bd_synthesize")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("soft_advice_voice" in (f.section or "") for f in warns)
