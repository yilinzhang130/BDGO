"""Schema validator tests for draft_codev mode."""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_CODEV = """# Co-Development Agreement — PEG-001 (Peg-Bio × BeiGene)

> ⚠️ **Not legal advice / 非法律意见** — Counsel review is mandatory.
>
> **All provisions BINDING upon execution.**

## 一、Parties / 当事方
- **Party A**: Peg-Bio
- **Party B**: BeiGene

## 二、Definitions / 定义
- **Affiliate**: standard
- **Co-Development Program**: PEG-001 development for NSCLC
- **Joint Steering Committee (JSC)**: 6-person body, 3 each
- **Background IP**: each party's pre-existing IP
- **Foreground IP**: arising from joint work
- **Joint IP**: jointly invented
- **Field**: oncology
- **Territory**: worldwide
- **Net Sales**: standard

## 三、Joint Development Plan & JSC / 共同开发计划与 JSC
- **Composition**: 3 reps each party
- **Voting**: consensus required for major decisions, majority for routine
- **Deadlock**: CEO escalation within 30 days; if unresolved → arbitration
- **Cadence**: monthly during dev / quarterly post-launch

## 四、Cost Sharing & Funding / 成本分摊与资金安排
- **Cost Split Model**: 50/50 — Party A 50%, Party B 50%
- **Annual Budget**: JSC approves; >10% overrun re-budgeted
- **Audit**: each party may audit annually with 30 days notice

## 五、IP Ownership & Improvements / IP 归属与改进
- **Background IP**: each party retains
- **Foreground IP**: jointly owned
- **Joint IP**: free-license-back to each party for own field
- **Improvements**: each party's improvements to its own Background IP retained

## 六、Commercialization & Territory / 商业化与地域
- **Model**: Joint worldwide commercialization
- **Cross-Border**: supply chain coordinated; pricing harmonized
- **Marketing**: joint brand / marketing budget split per cost ratio

## 七、Diligence / 勤勉义务
Both parties commit to CRE. Quantitative milestones at JSC level. Failure
triggers JSC review and potential leadership transfer.

## 八、Confidentiality / 保密
Mutual; 7 years post termination; standard exceptions.

## 九、Reps & Warranties + Indemnification / 陈述保证与赔偿
Each party reps IP ownership / non-infringement / authority.
Mutual indemnification — each indemnifies for own Background IP claims.
Cap at 1× cumulative spend.

## 十、Term & Termination + Effects / 期限、终止与终止效果
- Term: until last-to-expire Joint Patent
- Termination: material breach / insolvency / change of control (90-day cure)
- Effects: Joint IP license-back to non-breaching party for own use; survival
  of confidentiality, accrued obligations, IP, governing law.

## 十一、Buyout / Change-of-Control / 收购选择权
- **Trigger**: change of control / strategic divergence / 3-year stagnation
- **Mechanism**: either may offer fair-market-value buyout
- **FMV**: independent investment-bank appraisal
- **ROFR**: 90 days for the other side to match

## 十二、Governing Law & Misc / 适用法律 + 杂项
- Governing Law: Hong Kong
- Dispute Resolution: HKIAC arbitration, English language
- Notices / Assignment / Force Majeure / Severability standard

## 商业风险提示

1. **JSC deadlock** — 长期无法决策的成本
2. **Cost overrun** — 实际超过 baseline 的处理
3. **Partner change-of-control** — 对方被并购时我方权利
4. **IP attribution** — 联合发明归属争议
5. **Commercialization conflict** — split-territory 时的协调

## 签署前 Checklist
- [ ] 律师 review (含跨境税务)
- [ ] BD + R&D + 财务三方对齐
- [ ] IP 团队确认 Foreground IP 分配
- [ ] 内部 JSC 提名人选确认
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_CODEV, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_jsc_without_voting_fails():
    md = WELL_FORMED_CODEV.replace(
        "- **Voting**: consensus required for major decisions, majority for routine\n"
        "- **Deadlock**: CEO escalation within 30 days; if unresolved → arbitration\n",
        "- General governance arrangements.\n",
    )
    audit = validate_markdown(md, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "jsc" for f in fails)


def test_validator_cost_sharing_without_audit_fails():
    md = WELL_FORMED_CODEV.replace(
        "- **Audit**: each party may audit annually with 30 days notice\n", ""
    )
    audit = validate_markdown(md, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "cost_sharing" for f in fails)


def test_validator_ip_without_background_fails():
    md = (
        WELL_FORMED_CODEV.replace("- **Background IP**: each party retains\n", "")
        .replace("- **Background IP**: each party's pre-existing IP\n", "")
        .replace("Background", "Pre-existing")
    )
    audit = validate_markdown(md, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "ip_ownership" for f in fails)


def test_validator_buyout_without_fmv_fails():
    md = WELL_FORMED_CODEV.replace(
        "- **Mechanism**: either may offer fair-market-value buyout\n"
        "- **FMV**: independent investment-bank appraisal\n",
        "- **Mechanism**: standard buyout option\n",
    ).replace("appraisal", "review")
    audit = validate_markdown(md, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "buyout" for f in fails)


def test_validator_only_4_risks_fails():
    md = WELL_FORMED_CODEV.replace(
        "5. **Commercialization conflict** — split-territory 时的协调\n", ""
    )
    audit = validate_markdown(md, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "commercial_risks" for f in fails)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_CODEV.replace(
        "PEG-001 development for NSCLC",
        "industry-leading PEG-001 development for NSCLC",
    )
    audit = validate_markdown(md, mode="draft_codev")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_twelve_sections_all_required():
    md = WELL_FORMED_CODEV
    md = md.replace("## 七、Diligence / 勤勉义务", "## XYZZY1")
    md = md.replace("## 十一、Buyout / Change-of-Control / 收购选择权", "## XYZZY2")
    audit = validate_markdown(md, mode="draft_codev")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"diligence", "buyout"} <= fail_sections
