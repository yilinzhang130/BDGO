"""Schema validator tests for draft_mta mode (12-section MTA draft)."""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_MTA = """# Material Transfer Agreement — PEG-001 (Peg-Bio → Stanford University)

> ⚠️ **Not legal advice / 非法律意见** — Counsel review is mandatory before signing.

## 一、Parties / 当事方
[BINDING]
- **Provider / 材料提供方**: Peg-Bio
- **Recipient / 材料接收方**: Stanford University

## 二、Material Definition / 标的材料定义
[BINDING]
- **Material**: PEG-001 (humanized anti-PD1 IgG4 mAb)
- **Type**: antibody
- **Includes**: 仅原始 Material；衍生物 / 修饰物 / progeny 由后续条款规范

## 三、Research Use / 研究用途
[BINDING]

仅限于 Combination Study with anti-CTLA4 项目；禁止用于商业开发或第三方分享。

## 四、Disclosure / Know-How / 信息披露
[BINDING]

Provider 仅披露完成本研究项目所必需的 Material 表征数据。

## 五、Derivatives & Modifications / 衍生物与修饰物
[BINDING]

Joint ownership：双方共有衍生物 IP 由后续协议商定。Progeny 归 Provider。

## 六、IP Ownership / IP 归属
[BINDING]
- **Background IP**: 各自保留
- **Foreground IP** (research-generated): 与 Material 直接相关者归 Provider；其他双方共有
- **Joint Inventions**: license 互授

## 七、Publications / 发表
[BINDING]
- **Review Window**: 30 days
- Provider 仅可要求删除 CI 或推迟以保护 IP 申请；不得无理拒绝

## 八、Confidentiality / 保密
[BINDING]

双向；CI 定义按各方书面标记；保密期 7 年。

## 九、Material Return / Destruction / 材料返还/销毁
[BINDING]

项目结束 60 天内 Recipient 须 destroy 剩余 Material 并出具 certificate.

## 十、Term & Termination / 期限与终止
[BINDING]

- Term: 12 months
- Either party may terminate on 30 days written notice. 存续条款保留 (Confidentiality, IP, 责任限制).

## 十一、Reps & Warranties + Limitations
[BINDING]

Provider 不保证 Material 适合特定用途；Recipient 自担风险；间接损失豁免.

## 十二、Governing Law & Dispute Resolution
[BINDING]
- Governing Law: Hong Kong
- Dispute Resolution: HKIAC arbitration, English language

## 商业风险提示

1. **MTA-as-stealth-license** — 限定 Research Use，避免 "for any purpose"
2. **Derivative ownership ambiguity** — 已使用 "joint" 但建议在 follow-up 协议中明确
3. **Publication veto power** — 30 天 review window 在合理范围

## 签署前 Checklist
- [ ] 律师 review (含 IP / FTO 影响)
- [ ] 研发团队确认 Material 范围
- [ ] IP 团队签 off Foreground 归属
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_MTA, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_missing_section_fails():
    """Replace heading entirely (no 七、, no Publications, no 发表)
    so neither heading_pattern matches."""
    md = WELL_FORMED_MTA.replace("## 七、Publications / 发表", "## ZZZ section removed")
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "publications" for f in fails)


def test_validator_missing_binding_on_confidentiality_fails():
    md = WELL_FORMED_MTA.replace(
        "## 八、Confidentiality / 保密\n[BINDING]\n",
        "## 八、Confidentiality / 保密\n",
    )
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "confidentiality" for f in fails)


def test_validator_missing_binding_on_governing_law_fails():
    md = WELL_FORMED_MTA.replace(
        "## 十二、Governing Law & Dispute Resolution\n[BINDING]\n",
        "## 十二、Governing Law & Dispute Resolution\n",
    )
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "governing_law" for f in fails)


def test_validator_publications_without_review_window_fails():
    """Publications section without any time-window mention should FAIL."""
    md = WELL_FORMED_MTA.replace(
        "- **Review Window**: 30 days\n"
        "- Provider 仅可要求删除 CI 或推迟以保护 IP 申请；不得无理拒绝\n",
        "- 标准 publication review。\n",
    )
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "publications" for f in fails)


def test_validator_material_return_without_mechanism_fails():
    """Material Return section without 'return/destroy/certificate' fails.

    Note the section heading itself contains 销毁/Material Return/Destruction,
    so we must replace BOTH the heading (to a placeholder that still matches
    the heading_pattern via the numbered prefix) AND the body keywords.
    Easiest: replace heading body to drop the keywords but keep the 九、
    numerical so the section is still detected."""
    # Strip body-mechanism keywords AND the heading keywords (both in the
    # section text region). Use a heading WITHOUT 'Material Return/销毁/destroy'
    # — keep just '九、' so the section is detected via the numbered heading pattern.
    md = WELL_FORMED_MTA.replace(
        "## 九、Material Return / Destruction / 材料返还/销毁\n[BINDING]\n\n"
        "项目结束 60 天内 Recipient 须 destroy 剩余 Material 并出具 certificate.",
        "## 九、ZZZ\n[BINDING]\n\nRecipient 自行处理。",
    )
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "material_return" for f in fails)


def test_validator_missing_third_risk_fails():
    md = WELL_FORMED_MTA.replace(
        "3. **Publication veto power** — 30 天 review window 在合理范围\n", ""
    )
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "commercial_risks" for f in fails)


def test_validator_missing_lawyer_in_checklist_fails():
    """Strip ALL lawyer/IP/legal mentions from checklist (the schema
    accepts 律师 OR counsel OR legal OR IP team)."""
    md = WELL_FORMED_MTA.replace(
        "## 签署前 Checklist\n"
        "- [ ] 律师 review (含 IP / FTO 影响)\n"
        "- [ ] 研发团队确认 Material 范围\n"
        "- [ ] IP 团队签 off Foreground 归属\n",
        "## 签署前 Checklist\n- [ ] 内部审批\n- [ ] 财务确认\n- [ ] 高管 sign off\n",
    )
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "pre_signing_checklist" for f in fails)


def test_validator_for_any_purpose_warns():
    """The MTA-as-stealth-license red flag must be caught."""
    md = WELL_FORMED_MTA.replace(
        "仅限于 Combination Study with anti-CTLA4 项目",
        "Recipient 可使用 Material for any purpose",
    )
    audit = validate_markdown(md, mode="draft_mta")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("any_purpose" in (f.section or "") for f in warns)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_MTA.replace(
        "PEG-001 (humanized anti-PD1 IgG4 mAb)",
        "PEG-001 (industry-leading anti-PD1)",
    )
    audit = validate_markdown(md, mode="draft_mta")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_twelve_sections_all_required():
    """Drop multiple sections → multiple section_missing fails."""
    md = WELL_FORMED_MTA
    md = md.replace("## 五、Derivatives & Modifications / 衍生物与修饰物", "## XYZZY1")
    md = md.replace("## 七、Publications / 发表", "## XYZZY2")
    md = md.replace("## 十一、Reps & Warranties + Limitations", "## XYZZY3")
    audit = validate_markdown(md, mode="draft_mta")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"derivatives", "publications", "reps_warranties"} <= fail_sections
