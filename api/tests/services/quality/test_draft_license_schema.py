"""Schema validator tests for draft_license mode (13-section License)."""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_LICENSE = """# License Agreement — PEG-001 (Peg-Bio → Eli Lilly)

> ⚠️ **Not legal advice / 非法律意见** — Counsel review is mandatory before signing.
>
> **All provisions BINDING upon execution.**

## 一、Parties / 当事方
- Licensor / 授权方: Peg-Bio
- Licensee / 被授权方: Eli Lilly

## 二、Definitions / 定义
- **Affiliate / 关联方**: any entity controlling, controlled by, or under common control
- **Licensed Product / 许可产品**: PEG-001 and any product containing it
- **Net Sales / 净销售**: gross sales less returns, taxes, freight, allowances
- **Field / 领域**: Oncology indications
- **Territory / 地域**: Worldwide ex-China
- **Effective Date / 生效日**: signing date
- **Phase**: clinical phase as defined by FDA / EMA
- **Sublicense / 转许可**: any third-party right granted under this License

## 三、License Grant / 许可授予
Licensor grants Licensee an exclusive, royalty-bearing license under the
Licensed IP to develop, make, use and sell Licensed Product in the Field
in the Territory.

## 四、Sublicense / 转许可
Licensee may grant sublicenses with prior written consent of Licensor.
Sublicensee terms must be no less protective. Licensor receives 30% of
sublicense income.

## 五、Diligence Obligations / 勤勉义务
| Milestone | Target Date |
|---|---|
| IND filing | within 12 months of Effective Date |
| Phase 2 entry | within 24 months |
| NDA submission | within 60 months |
First commercial sale within 84 months. Failure triggers reversion.

## 六、Financial Terms / 财务条款
- **Upfront**: $50M
- **Equity**: 2.5%
- **Dev Milestones**: IND $5M; Phase 2 entry $20M; NDA submission $50M
- **Sales Milestones**: First $100M $25M; $500M $75M
- **Royalty**: tiered — <$100M: 8%, $100M-500M: 12%, >$500M: 15%
- **Royalty Term**: 10 years post first commercial sale

## 七、Royalty Reports & Audit / 销售报告与审计
Licensee provides quarterly reports within 60 days of quarter end.
Licensor may audit once per year with 30 days notice. Errors > 5% → Licensee
bears audit cost.

## 八、Patent Prosecution & Enforcement / 专利申请与执行
Licensor leads prosecution of Licensed Patents at Licensor's cost.
Licensor leads enforcement; Licensee may join. Recoveries split 60/40.

## 九、Improvements & New IP / 改进与新 IP
Background IP retained by each party. Foreground IP relating to Licensed
Product owned by Licensee with grant-back to Licensor for non-Field uses.
Joint inventions jointly owned with bilateral free-license-back.

## 十、Confidentiality / 保密
Mutual confidentiality. 7-year survival post termination. Standard exceptions.

## 十一、Reps & Warranties + Indemnification / 陈述保证与赔偿
Licensor reps: IP ownership, non-infringement, no encumbrance.
Indemnification mutual; Licensee indemnifies for product liability;
Licensor indemnifies for IP claims. Cap at 2× upfront.

## 十二、Term & Termination + Effects / 期限、终止与终止效果
- Term: until expiration of last-to-expire Licensed Patent
- Termination: material breach (90-day cure) / insolvency / change of control
- **Effects of Termination**: sublicensees in good standing survive direct to
  Licensor. Already-paid milestones non-refundable. Survival: confidentiality
  (7 years), accrued royalties, indemnification, governing law.

## 十三、Governing Law & Dispute Resolution + Misc / 适用法律 + 杂项
- Governing Law: Hong Kong
- Dispute Resolution: arbitration in HKIAC, English language, 3 arbitrators
- Notices: written; Assignment: with consent (acquiror exception);
  Force Majeure standard; Entire Agreement; Severability

## 商业风险提示

1. **Royalty stacking** — third-party licenses may stack onto Licensee's costs (>15%); recommend stacking cap protection
2. **Diligence triggers** — IND-within-12-months tight given current Phase status; recommend negotiating cure period
3. **Sublicense economics** — 30% of sublicense income may exceed pro-rata royalty for low-margin sublicensees
4. **Change-of-control** — automatic termination on Licensee CoC may scare strategic acquirers; consider opt-out
5. **Net Sales definition** — exclusion list narrow vs market norm; could understate royalty base

## 签署前 Checklist
- [ ] 律师 review (含跨境税务 + IP 转让登记)
- [ ] CMC 团队确认 Field 范围与现有 license-out 不冲突
- [ ] BD 团队确认 financial 与内部 target 一致
- [ ] IP 团队确认无与 third-party license 冲突
- [ ] 财务团队确认 royalty 计算方法 + audit 流程
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_LICENSE, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_definitions_missing_net_sales_fails():
    md = WELL_FORMED_LICENSE.replace(
        "- **Net Sales / 净销售**: gross sales less returns, taxes, freight, allowances\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "definitions" for f in fails)


def test_validator_financial_terms_missing_royalty_fails():
    md = WELL_FORMED_LICENSE.replace(
        "- **Royalty**: tiered — <$100M: 8%, $100M-500M: 12%, >$500M: 15%\n"
        "- **Royalty Term**: 10 years post first commercial sale\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "financial_terms" for f in fails)


def test_validator_only_4_risks_fails():
    """License needs ≥5 risks (vs ≥3 for TS/MTA)."""
    md = WELL_FORMED_LICENSE.replace(
        "5. **Net Sales definition** — exclusion list narrow vs market norm; could understate royalty base\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "commercial_risks" for f in fails)


def test_validator_termination_effects_without_survival_fails():
    """Strip every survival/存续/surviv signal from the document."""
    md = (
        WELL_FORMED_LICENSE.replace("survive", "end immediately")
        .replace("Survival:", "Post-termination:")
        .replace("存续", "立即终止")
    )
    audit = validate_markdown(md, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "term_termination_effects" for f in fails)


def test_validator_diligence_without_milestone_fails():
    """Diligence section must reference clinical milestones."""
    md = WELL_FORMED_LICENSE.replace(
        "## 五、Diligence Obligations / 勤勉义务\n"
        "| Milestone | Target Date |\n"
        "|---|---|\n"
        "| IND filing | within 12 months of Effective Date |\n"
        "| Phase 2 entry | within 24 months |\n"
        "| NDA submission | within 60 months |\n"
        "First commercial sale within 84 months. Failure triggers reversion.\n",
        "## 五、Diligence Obligations / 勤勉义务\nLicensee shall use reasonable efforts.\n",
    )
    audit = validate_markdown(md, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "diligence" for f in fails)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_LICENSE.replace(
        "Licensor grants Licensee an exclusive",
        "Licensor grants Licensee an industry-leading exclusive",
    )
    audit = validate_markdown(md, mode="draft_license")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_incomplete_drafting_warns():
    """'to be defined later' is a known License drafting bug."""
    md = WELL_FORMED_LICENSE.replace(
        "- **Net Sales / 净销售**: gross sales less returns",
        "- **Net Sales / 净销售**: to be defined later, gross sales less returns",
    )
    audit = validate_markdown(md, mode="draft_license")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("incomplete_drafting" in (f.section or "") for f in warns)


def test_validator_thirteen_sections_all_required():
    """Replace full heading line including Chinese suffix to break all
    heading_pattern alternations."""
    md = WELL_FORMED_LICENSE
    md = md.replace("## 七、Royalty Reports & Audit / 销售报告与审计", "## XYZZY1")
    md = md.replace("## 九、Improvements & New IP / 改进与新 IP", "## XYZZY2")
    md = md.replace("## 十一、Reps & Warranties + Indemnification / 陈述保证与赔偿", "## XYZZY3")
    audit = validate_markdown(md, mode="draft_license")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"royalty_audit", "improvements", "reps_indemnity"} <= fail_sections
