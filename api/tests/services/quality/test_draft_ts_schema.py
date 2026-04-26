"""
Schema validator tests for draft-ts mode.

Exercises the YAML-driven L0 audit against representative markdown samples
(well-formed, missing sections, missing BINDING tags, missing risks, etc.).
"""

from __future__ import annotations

from services.quality import validate_markdown

# A minimum well-formed TS markdown used as the baseline (passes 0 FAILs).
WELL_FORMED_TS = """# Term Sheet — PEG-001 (Peg-Bio → Eli Lilly)

> ⚠️ **Not legal advice / 非法律意见** — Counsel review is mandatory before signing.

## 一、Parties / 当事方
[Binding once signed]
- **Licensor / 授权方**: Peg-Bio
- **Licensee / 被授权方**: Eli Lilly

## 二、Subject Asset / 标的资产
[Non-Binding]
- Asset: PEG-001
- Indication: NSCLC

## 三、Field of Use / 适用范围
[Non-Binding]

Oncology only, including line extensions.

## 四、Territory / 地域
[Non-Binding]

Worldwide ex-China.

## 五、Exclusivity / 独占性
[Non-Binding]

Exclusive license. Sublicense permitted with prior written consent.

## 六、Financial Terms / 财务条款
[Non-Binding — headline ranges only]

| Component | Amount | Comparable Anchor |
|---|---|---|
| Upfront | $50M | typical Phase 2 ADC range $30-100M |
| Milestone | $300M | dev milestones |
| Royalty | 8-15% tiered | Phase 2 ADC typical |

## 七、Diligence Obligations / 勤勉义务
[Non-Binding]

CRE with quantitative milestones. First IND within 18 months.

## 八、IP Ownership & Improvements / IP 归属与改进
[Non-Binding]

Background IP retained by each party. Foreground IP jointly owned.

## 九、Reps & Warranties / 陈述与保证
[Non-Binding]

Standard reps including IP non-infringement.

## 十、Confidentiality / 保密
[**BINDING**] 具约束力

Refer to existing CDA. Confidentiality period: 5 years post-termination.

## 十一、Exclusivity / No-Shop / 排他期
[**BINDING**] 具约束力

- No-Shop Period: 60 days
- Break-up Fee: $5M

## 十二、Term & Termination / 期限与终止
[**BINDING (TS-level)** + Non-Binding (deal-level)] 具约束力

- TS Expiration: 90 days
- Deal Term: 15 years from first commercial sale

## 十三、Governing Law & Dispute Resolution / 适用法律与争议解决
[**BINDING**] 具约束力

- Governing Law: Hong Kong
- Dispute Resolution: HKIAC arbitration, English language

## 商业风险提示

1. **Royalty stacking** — 描述
2. **Sublicense economics** — 描述
3. **Diligence triggers** — 描述

## 签署前 Checklist
- [ ] 律师 review
- [ ] CMC 团队确认
"""


def test_validator_well_formed_passes_no_fails():
    """A complete, well-structured TS should produce 0 FAIL findings."""
    audit = validate_markdown(WELL_FORMED_TS, mode="draft_ts")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_missing_section_fails():
    """Removing a required section produces a section_missing FAIL."""
    md = WELL_FORMED_TS.replace(
        "## 七、Diligence Obligations / 勤勉义务\n[Non-Binding]\n\nCRE with quantitative milestones. First IND within 18 months.\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_ts")
    assert audit.n_fail >= 1
    assert any(f.section == "diligence" for f in audit.findings if f.severity == "fail")


def test_validator_missing_binding_tag_fails():
    """Confidentiality without BINDING marker should FAIL."""
    md = WELL_FORMED_TS.replace(
        "[**BINDING**] 具约束力\n\nRefer to existing CDA", "Refer to existing CDA"
    )
    audit = validate_markdown(md, mode="draft_ts")
    fails = [f for f in audit.findings if f.severity == "fail"]
    # Confidentiality section should fail the must_contain_all "BINDING" rule
    assert any(f.section == "confidentiality" for f in fails)


def test_validator_missing_risks_fails():
    """Remove the 3rd risk numbering → fail because need 1+2+3."""
    md = WELL_FORMED_TS.replace(
        "1. **Royalty stacking** — 描述\n2. **Sublicense economics** — 描述\n3. **Diligence triggers** — 描述\n",
        "1. **Royalty stacking** — 描述\n2. **Sublicense economics** — 描述\n",
    )
    audit = validate_markdown(md, mode="draft_ts")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "commercial_risks" for f in fails)


def test_validator_missing_checklist_lawyer_fails():
    """Checklist without 律师/counsel/legal mention should FAIL."""
    md = WELL_FORMED_TS.replace("- [ ] 律师 review", "- [ ] something else")
    audit = validate_markdown(md, mode="draft_ts")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "pre_signing_checklist" for f in fails)


def test_validator_marketing_hyperbole_warn():
    """'Fantastic' or '极具吸引力' triggers a marketing-hyperbole warn."""
    md = WELL_FORMED_TS.replace(
        "Refer to existing CDA",
        "Refer to existing CDA. This is a fantastic deal.",
    )
    audit = validate_markdown(md, mode="draft_ts")
    warns = [f for f in audit.findings if f.severity == "warn"]
    # Validator stores the rule's category in `section` (not `category` —
    # that one is the finding's high-level bucket like "banned_phrase").
    assert any(
        "marketing_hyperbole" in (f.section or "") or "hyperbole" in (f.section or "")
        for f in warns
    ), (
        f"Expected hyperbole warn, got: {[(f.severity, f.category, f.section) for f in audit.findings]}"
    )


def test_validator_financial_terms_must_have_amount():
    """Financial section without any $ / % / Upfront / Milestone / Royalty fails."""
    md = WELL_FORMED_TS.replace(
        "| Upfront | $50M | typical Phase 2 ADC range $30-100M |\n"
        "| Milestone | $300M | dev milestones |\n"
        "| Royalty | 8-15% tiered | Phase 2 ADC typical |\n",
        "(deal terms TBD)\n",
    )
    audit = validate_markdown(md, mode="draft_ts")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "financial_terms" for f in fails)


def test_validator_min_words_warn_on_short_section():
    """Section min_words is treated as warn (not fail) — regression test for the new validator extension."""
    # Use a schema dict directly so we can flex the new section-level
    # min_words rule without touching a real YAML file.
    from services.quality import schema_validator

    schema = {
        "report_type": "test",
        "sections": [
            {
                "id": "s1",
                "name": "Section 1",
                "heading_patterns": ["Section 1"],
                "required": True,
                "min_words": 100,
            }
        ],
    }
    # Monkeypatch a fake schema entry — easier to load via direct call
    blocks = schema_validator.load_md_text("# Section 1\n\nshort\n")
    sections = schema_validator.split_sections(blocks, schema)
    audit = schema_validator.AuditResult()
    schema_validator.check_sections(sections, schema, audit)
    # min_words triggers WARN, not FAIL
    assert audit.n_fail == 0
    assert any(f.severity == "warn" for f in audit.findings)
