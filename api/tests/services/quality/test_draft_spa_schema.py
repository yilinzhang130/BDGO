"""Schema validator tests for draft_spa mode (13-section M&A skeleton)."""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_SPA = """# Stock Purchase Agreement — TargetCo (Founders → Pfizer)

> ⚠️ **Not legal advice / 非法律意见** — This is a BD draft skeleton.
> SPA / APA / Merger agreements typically run 100+ pages. Counsel review mandatory.
>
> **All provisions BINDING upon execution.**

## 一、Parties / 当事方
- **Buyer / 买方**: Pfizer Inc.
- **Seller / 卖方**: Founders & VCs of TargetCo
- **Target / 标的**: TargetCo

## 二、Definitions / 定义
- **Affiliate / 关联方**: any entity controlling, controlled by, or under common control
- **Closing / 交割**: completion of the transactions hereunder
- **Closing Date**: the date on which Closing occurs
- **Material Adverse Change / MAC / 重大不利变化**: any event materially adverse to Target's business
- **Knowledge / 知悉**: actual knowledge of designated officers
- **Indemnified Party / 赔偿义务方**: the party seeking indemnification
- **Loss / 损失**: any damages, liabilities, costs, expenses
- **Working Capital Adjustment**: post-closing NWC reconciliation
- **Earnout**: contingent consideration payable on milestone achievement
- **Fundamental Reps**: capitalization, authority, ownership, no conflicts

## 三、Purchase Price & Adjustments / 收购价格与调整
- **Headline EV / 企业价值**: $500M
- **Cash at Closing / 现金对价**: $400M
- **Stock Consideration**: 20% of price
- **Working Capital Adjustment / 净营运资本调整**: target NWC ± 5% adjustment mechanism
- **Cash / Debt Adjustment**: dollar-for-dollar
- **Earnout**: up to $150M based on Phase 3 readout + first commercial sale

## 四、Closing Conditions / 交割条件
- **Regulatory Filings**: HSR clearance + CFIUS approval + SAMR clearance required
- **Third-Party Consents**: material in-license consents
- **No MAC**: Material Adverse Change clause triggers walk-away right
- **Bring-Down Reps**: reps remain true at Closing
- **Officer's Certificate**: Target CEO/CFO certification
- **Other Customary**: legal opinions / lien releases

## 五、Interim Period Covenants / 过渡期约定
- **Interim Period**: 6 months sign-to-close
- **Operating Restrictions**: ordinary course / no extraordinary actions / no dividends
- **Notification Obligations**: target notifies buyer of material events
- **Exclusivity (No-Shop)**: 90 days standard

## 六、Reps & Warranties — Fundamentals / 基础陈述保证
（uncapped, 6-year survival）
- **Capitalization & Ownership / 股权结构与所有权**: cap table accuracy + no liens
- **Authority & Enforceability / 授权与可执行性**: corporate authority to execute
- **No Conflicts**: execution does not breach contracts or law
- **Title to Shares / Assets**: clean title

## 七、Reps & Warranties — General Business / 一般商业陈述保证
（cap + 18-month survival）
- **Financial Statements / 财务报表**: GAAP compliance, no undisclosed liabilities
- **Tax / 税务**: filings current, no audits
- **IP / Intellectual Property / 知识产权**: ownership, no infringement, employee assignments
- **Employees & ERISA**: no material claims
- **Litigation**: no material pending matters
- **Material Contracts**: list and absence of breach
- **Regulatory & Compliance**: FDA / EMA standing
- **Permits & Licenses**: all material permits in good standing

## 八、Indemnification / 赔偿
- **Cap / 上限**: 15% of purchase price (general reps; fundamentals uncapped)
- **Basket / 篮子 / 起赔**: $0.5M deductible
- **Tipping**: yes — once basket exceeded, recovery from dollar one
- **Survival / 存续**:
  - General R&W: 18 months
  - Fundamentals: 6 years
  - Tax: until statute of limitations
- **Exclusive Remedy**: indemnification is sole remedy except for fraud
- **Source of Recovery**: 8% escrow + R&W insurance for excess

## 九、Termination / 终止
- **Triggers**:
  - Mutual consent
  - Outside Date / Drop-Dead Date — 9 months from signing
  - Failure of Closing Conditions
  - MAC trigger (per config)
- **Termination Fee / 终止费**: 3% of EV (typical biotech)
- **Reverse Termination Fee**: 5% if Buyer financing/regulatory walks

## 十、Tax Matters / 税务
- **Tax Treatment**: stock purchase with 338(h)(10) election
- **Pre-Closing Taxes**: Seller bears
- **Post-Closing Taxes**: Buyer bears
- **Tax Returns**: Buyer prepares post-closing
- **Tax Indemnification**: uncapped, until statute of limitations

## 十一、Post-Closing Covenants / 交割后约定
- **Non-Compete / 竞业禁止**: 24 months for Seller's principals
- **Non-Solicit / 非招揽**: 24 months
- **Confidentiality**: 5 years post-closing
- **Cooperation**: tax, litigation, transition support
- **Releases**: mutual releases of pre-closing claims

## 十二、Escrow & Insurance / 托管与保险
- **Indemnity Escrow / 托管**: 8% of price for 18 months
- **R&W Insurance / 保险**: $50M policy, 1.5% premium, replaces indemnity escrow above cap
- **Special Indemnity Escrow**: $5M for known IP litigation

## 十三、Governing Law & Dispute Resolution / 适用法律与争议解决
- **Governing Law / 适用法律**: Delaware
- **Forum**: Delaware Court of Chancery
- **Specific Performance**: equitable remedy available
- **Notices / Assignment / Misc**: standard

## 商业风险提示

仅 for buyer 视角，不是法律意见：

1. **Closing certainty** — HSR + CFIUS + SAMR triple filings ⇒ 6-9 months earliest close; recommend reverse termination fee
2. **Earnout dispute** — Phase 3 readout calibration is post-closing's biggest fight; recommend pre-defined statistical SAP
3. **R&W gap risk** — fundamentals vs general boundary disputes; recommend wide fundamentals definition
4. **Working capital adjustment** — target NWC anchor must reflect 12-month run-rate, not snapshot
5. **Interim period restriction** — 6 months of operating covenants risks competitive degradation
6. **Cap/basket asymmetry** — 15% cap + $0.5M basket favors seller; consider 20%+ for high-IP-risk assets

## 签署前 Checklist
- [ ] M&A 律师 review (含 antitrust + 跨境税务)
- [ ] 财务 / 审计 review (Working Capital + financial reps)
- [ ] R&W insurance broker quote (1.5% premium typical)
- [ ] 监管 filing 准备（HSR / CFIUS / SAMR）
- [ ] Disclosure Schedule 内部 review
- [ ] BD 团队确认 strategic fit + post-closing integration plan
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_SPA, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_definitions_missing_mac_fails():
    md = WELL_FORMED_SPA.replace(
        "- **Material Adverse Change / MAC / 重大不利变化**: any event materially adverse to Target's business\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "definitions" for f in fails)


def test_validator_purchase_price_missing_nwc_fails():
    """Working Capital Adjustment is signature SPA mechanic."""
    md = WELL_FORMED_SPA.replace(
        "- **Working Capital Adjustment / 净营运资本调整**: target NWC ± 5% adjustment mechanism\n",
        "",
    ).replace("- **Working Capital Adjustment**: post-closing NWC reconciliation\n", "")
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "purchase_price" for f in fails)


def test_validator_indemnification_missing_basket_fails():
    """Cap + basket + survival three-tuple is mandatory."""
    md = (
        WELL_FORMED_SPA.replace(
            "- **Basket / 篮子 / 起赔**: $0.5M deductible\n",
            "",
        )
        # also strip the secondary "basket" mention so the keyword truly absent
        .replace(
            "- **Tipping**: yes — once basket exceeded, recovery from dollar one\n",
            "- **Tipping**: yes — once threshold exceeded, recovery from dollar one\n",
        )
    )
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "indemnification" for f in fails)


def test_validator_indemnification_missing_cap_fails():
    md = WELL_FORMED_SPA.replace(
        "- **Cap / 上限**: 15% of purchase price (general reps; fundamentals uncapped)\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "indemnification" for f in fails)


def test_validator_post_closing_missing_non_compete_fails():
    md = WELL_FORMED_SPA.replace(
        "- **Non-Compete / 竞业禁止**: 24 months for Seller's principals\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "post_closing" for f in fails)


def test_validator_only_5_risks_fails():
    """SPA needs ≥6 risks (vs ≥5 for license, ≥3 for TS/MTA)."""
    md = WELL_FORMED_SPA.replace(
        "6. **Cap/basket asymmetry** — 15% cap + $0.5M basket favors seller; consider 20%+ for high-IP-risk assets\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "commercial_risks" for f in fails)


def test_validator_rw_general_missing_ip_fails():
    """General R&W section must include both Financial and IP."""
    md = WELL_FORMED_SPA.replace(
        "- **IP / Intellectual Property / 知识产权**: ownership, no infringement, employee assignments\n",
        "",
    )
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "rw_general" for f in fails)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_SPA.replace(
        "Pfizer Inc.",
        "Pfizer Inc. (industry-leading)",
    )
    audit = validate_markdown(md, mode="draft_spa")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_incomplete_drafting_warns():
    """'to be defined later' is a known SPA drafting bug."""
    md = WELL_FORMED_SPA.replace(
        "**Working Capital Adjustment**: post-closing NWC reconciliation",
        "**Working Capital Adjustment**: to be defined later, post-closing NWC reconciliation",
    )
    audit = validate_markdown(md, mode="draft_spa")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("incomplete_drafting" in (f.section or "") for f in warns)


def test_validator_thirteen_sections_all_required():
    """Replace full heading lines (incl. Chinese suffix) to break detection."""
    md = WELL_FORMED_SPA
    md = md.replace("## 五、Interim Period Covenants / 过渡期约定", "## XYZZY1")
    md = md.replace("## 十、Tax Matters / 税务", "## XYZZY2")
    md = md.replace("## 十二、Escrow & Insurance / 托管与保险", "## XYZZY3")
    audit = validate_markdown(md, mode="draft_spa")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"interim_covenants", "tax_matters", "escrow_insurance"} <= fail_sections
