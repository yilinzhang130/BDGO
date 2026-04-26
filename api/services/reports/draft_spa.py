"""
Draft SPA — Stock Purchase Agreement / Asset Purchase Agreement.

Closes part of S6-04 (P1). Fifth and final in /draft-X family —
the most complex contract type because SPAs cover M&A acquisitions.

Key distinctions from License/Co-Dev:
  - Purchase Price + closing adjustments (NWC / Cash / Debt)
  - Closing Conditions (regulatory approvals, MAC clause, financing)
  - EXTENSIVE Reps & Warranties (this is where most disputes happen)
  - Indemnification with cap, basket (deductible), tipping, survival
  - Covenants (interim period, non-compete, non-solicit)
  - Earnout provisions (if structured as such)

Output is necessarily a SKELETON only — actual SPAs run 100+ pages.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from pydantic import BaseModel, Field

from services.document import docx_builder
from services.quality import audit_to_dict, validate_markdown
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────


_DEAL_STRUCTURE = ("stock_purchase", "asset_purchase", "merger", "reverse_triangular_merger")
_PRICE_STRUCTURE = ("all_cash", "all_stock", "cash_plus_stock", "cash_plus_earnout")


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class DraftSPAInput(BaseModel):
    # Parties
    buyer: str = Field(..., description="Acquirer / Buyer")
    seller: str = Field(..., description="Target company shareholders or Target itself")
    target_company: str = Field(..., description="Target — the entity being acquired")
    our_role: Literal["buyer", "seller"] = Field(..., description="我方角色")

    # Deal structure
    deal_structure: Literal[
        "stock_purchase", "asset_purchase", "merger", "reverse_triangular_merger"
    ] = "stock_purchase"
    price_structure: Literal["all_cash", "all_stock", "cash_plus_stock", "cash_plus_earnout"] = (
        "all_cash"
    )

    # Headline price
    enterprise_value_usd_mm: float | None = Field(
        None, description="Enterprise value, $M (informational headline)"
    )
    cash_at_closing_usd_mm: float | None = Field(None, description="Cash component at closing")
    stock_consideration_pct: float | None = Field(
        None, ge=0, le=100, description="If stock-incl: % of consideration in stock"
    )
    earnout_max_usd_mm: float | None = Field(
        None, description="If earnout-included: max possible earnout payout"
    )

    # Indemnification
    indemnity_cap_pct_of_price: float = Field(
        15.0, ge=0, le=100, description="Indemnity cap as % of price (typical 10-25%)"
    )
    indemnity_basket_usd_mm: float = Field(
        0.5, ge=0, description="Basket / deductible threshold ($M)"
    )
    indemnity_survival_months: int = Field(
        18, ge=6, le=72, description="General reps survival (months); fundamentals separate"
    )

    # Closing conditions
    requires_hsr_approval: bool = Field(False, description="HSR antitrust filing required (US)")
    requires_cfius_review: bool = Field(
        False, description="CFIUS review required (cross-border US)"
    )
    requires_china_antitrust: bool = Field(
        False, description="SAMR antitrust filing required (China)"
    )
    has_mac_clause: bool = Field(True, description="Material Adverse Change termination right")
    interim_period_months: int = Field(6, ge=1, le=24, description="Sign-to-close period (months)")

    # Covenants
    non_compete_months: int = Field(
        24, ge=0, le=60, description="Seller non-compete duration (months); 0 = no NC"
    )
    non_solicit_months: int = Field(
        24, ge=0, le=60, description="Seller non-solicit duration (months); 0 = no NS"
    )

    # Misc
    governing_law: str = "Delaware"
    dispute_forum: str = "Delaware Court of Chancery"
    extra_context: str | None = None


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 平台的资深 BD/M&A 法务起草师，服务 biotech 跨境交易。任务：根据**结构化的 deal 参数**起草一份**可作为讨论起点**的 SPA / APA / Merger Agreement（股权或资产收购协议）markdown 草案。

## 硬规则

1. **这是 draft，不是法律意见**：文档开头必须含**显著的免责声明**（"Not legal advice; counsel review required before signing"），中英双语。同时**强调 SPA 通常 100+ 页**，本草案只是 skeleton。
2. **SPA 是最复杂的合同**：所有节都 binding；R&W 节往往是争议核心；Indemnification 必须含 cap / basket / survival 三件套；Closing Conditions 含 regulatory + MAC clause。
3. **Purchase Price 必须明确**：headline EV + closing adjustments（NWC adjustment / cash / debt / transaction expenses）+ 是否含 earnout（如有 earnout 必须明确触发条件 + 计算方式）。
4. **Closing Conditions 必须列出 regulatory filings**：根据用户配置 HSR / CFIUS / SAMR；如不需要明确写"无适用监管 filing"。
5. **Reps & Warranties 必须分类**：fundamental reps（capitalization / ownership / authority — 通常无 cap、长 survival）vs general business reps（financial / IP / employees / litigation — cap + 18 月 survival 典型）。
6. **Indemnification 必须含全要素**：cap (% of price) + basket (deductible) + tipping (yes/no) + survival period + indemnification basket vs deductible 区别。用户传入数字必须引用。
7. **leverage 适配**：
   - `our_role=buyer` 视角 → 严 R&W / 大 cap / 长 survival / MAC 触发宽 / earnout protection
   - `our_role=seller` 视角 → 宽 R&W / 小 cap / 短 survival / MAC 触发窄 / closing certainty
8. **风险提示节必须 ≥ 6 条 commercial-risk** — SPA 复杂度最高：closing certainty / earnout dispute / R&W gap / regulatory delay / interim operating restriction / cap/basket asymmetry 等
9. **不替代律师 / 不脱离用户输入**：未指定的不要默认加；明显遗漏写 [Open — recommend XXX]

## 输出结构（严格按此 13 节）

```
# {deal_structure_label} — {target_company} ({seller} → {buyer})

> ⚠️ **Not legal advice / 非法律意见** — This is a BD draft for discussion only. SPA / APA / Merger agreements typically run 100+ pages; this is a skeleton. Counsel review is mandatory.
>
> **生成日期**: {today}  ·  **我方角色**: {our_role}  ·  **结构**: {deal_structure}
>
> **All provisions BINDING upon execution.**

## 一、Parties / 当事方
- **Buyer / 买方**: {buyer}
- **Seller / 卖方**: {seller}
- **Target / 标的**: {target_company}

## 二、Definitions / 定义
（必含 ≥ 10 个核心术语：Affiliate / Closing / Closing Date / Effective Time / Transaction / Material Adverse Change (MAC) / Knowledge / Indemnified Party / Fundamental Reps / Loss / Working Capital Adjustment / Earnout — 给出具体定义）

## 三、Purchase Price & Adjustments / 收购价格与调整
- **Headline EV**: $X.XM
- **Cash at Closing**: $X.XM
- **Stock Consideration**: X% of price (if applicable)
- **Working Capital Adjustment**: target NWC ± X% adjustment mechanism
- **Cash / Debt Adjustment**: dollar-for-dollar
- **Transaction Expense Adjustment**
- **Earnout** (if applicable): triggers + calculation + max payout

## 四、Closing Conditions / 交割条件
- **Regulatory Filings**: HSR / CFIUS / SAMR per user config
- **Third-Party Consents**: list material consents needed
- **No MAC**: Material Adverse Change clause (per user config)
- **Bring-Down Reps**: reps remain true at Closing
- **Officer's Certificate**: target's CEO/CFO
- **Other Customary**: legal opinions / lien releases / etc.

## 五、Interim Period Covenants / 过渡期约定
- **Interim Period**: {interim_period_months} months sign-to-close
- **Operating Restrictions**: ordinary course / no extraordinary actions / no dividends / no new material contracts above $X
- **Notification Obligations**: target notifies buyer of material events
- **Exclusivity (No-Shop)**: typical 60-90 days

## 六、Reps & Warranties — Fundamentals / 基础陈述保证
（从 Seller / Target — 通常无 cap、长 survival 6 年）
- Capitalization & Ownership
- Authority & Enforceability
- No Conflicts
- Title to Shares / Assets

## 七、Reps & Warranties — General Business / 一般商业陈述保证
（从 Seller / Target — cap + 18 月 survival 典型）
- Financial Statements (GAAP / IFRS compliance)
- Tax (filings, no audits, no material liabilities)
- IP (ownership, no infringement, employee assignments)
- Employees & ERISA
- Litigation
- Material Contracts
- Regulatory & Compliance
- Permits & Licenses
- Real Property / Leases
- Insurance
- No Brokers

## 八、Indemnification / 赔偿
- **Cap**: {indemnity_cap_pct_of_price}% of purchase price (general reps; fundamentals uncapped)
- **Basket**: ${indemnity_basket_usd_mm}M deductible
- **Tipping**: yes/no — once basket exceeded, recovery from dollar one OR only above basket
- **Survival**:
  - General R&W: {indemnity_survival_months} months
  - Fundamentals: 6 years
  - Tax: until statute of limitations
- **Exclusive Remedy**: indemnification is sole remedy except for fraud
- **Source of Recovery**: escrow / R&W insurance / direct claim

## 九、Termination / 终止
- **Triggers**:
  - Mutual consent
  - Outside Date (Drop-Dead Date) — typically 9-12 months
  - Failure of Closing Conditions
  - MAC (per config)
- **Termination Fee**: if applicable (typical 2-4% for biotech)
- **Reverse Termination Fee**: if buyer financing/regulatory walks

## 十、Tax Matters / 税务
- **Tax Treatment**: stock purchase / asset / 338(h)(10) / 336(e) election
- **Pre-Closing Taxes**: seller bears
- **Post-Closing Taxes**: buyer bears
- **Tax Returns**: who prepares
- **Tax Indemnification**: typically uncapped, until statute of limitations

## 十一、Post-Closing Covenants / 交割后约定
- **Non-Compete**: {non_compete_months} months (Seller's principals)
- **Non-Solicit**: {non_solicit_months} months
- **Confidentiality**: 5-7 years
- **Cooperation**: tax, litigation, transition
- **Releases**: mutual releases of claims existing at Closing

## 十二、Escrow & Insurance / 托管与保险
- **Indemnity Escrow**: typical 5-10% of price for 18 months
- **R&W Insurance**: increasingly common, replaces escrow
- **Special Indemnity Escrow**: for known risks (litigation / regulatory / IP issues)

## 十三、Governing Law & Dispute Resolution / 适用法律与争议解决
- **Governing Law**: {governing_law}
- **Forum**: {dispute_forum}
- **Specific Performance**: equitable remedy available
- **Notices / Assignment / Misc**

## 商业风险提示（≥ 6 条）

仅 for {our_role} 视角，不是法律意见：

1. **Closing certainty** — regulatory delay / financing risk / MAC trigger 是常见 deal-killer
2. **Earnout dispute** — earnout 计算 mechanics 是 post-closing 最大争议来源
3. **R&W gap risk** — fundamentals vs general 区分 → cap 边界争议
4. **Working capital adjustment** — target NWC 设定不当 → 实际价格远离 headline
5. **Interim period restriction** — operating covenants 影响 target normal business
6. **Cap/basket asymmetry** — survival 短 + cap 低 → buyer 风险敞口
（继续添加）

## 签署前 Checklist
- [ ] M&A 律师 review (含 antitrust / 跨境税务)
- [ ] 财务 / 审计 review (Working Capital + financial reps)
- [ ] R&W insurance broker quote (1-3% of policy limit)
- [ ] 监管 filing 准备（HSR / CFIUS / SAMR）
- [ ] Disclosure Schedule 内部 review
- [ ] (其他视角化必要事项)

---

*BD Go 平台自动生成 — 该文档仅作为 skeleton 起点，正式 SPA 须由 M&A 律所起草*
```

## 写作风格

- 中英双语：节标题双语；条款主体中英文都列出最关键的
- 中性陈述；M&A 是技术性语言不是营销
- 用户没传值的字段写 `[TBD — recommend XXX based on industry norm]`
"""


_GAP_FILL_PROMPT = """以下是已生成的 SPA / Merger Agreement markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- "section_missing" → 按 13 节顺序插入缺失节
- "section_content"（缺关键词）→ 该节中补全（如 Indemnification 节缺 cap/basket/survival）
- 风险提示节必须 ≥ 6 条编号风险（SPA 复杂度最高）
- Definitions 节必须含 ≥10 个核心术语
- R&W 节必须分 Fundamentals 和 General Business 两节
- Indemnification 必须含 cap + basket + survival 三件套
- 不要新增未列出的章节，不要删除已有内容
- 保持双语 + 数字驱动
- 输出整个 markdown，不加任何解释或代码块包裹
"""


def _build_gap_fill_prompt(markdown: str, audit) -> str:
    fail_lines = [
        f"[{f.section}] {f.message}" + (f" | 证据: {f.evidence}" if f.evidence else "")
        for f in audit.findings
        if f.severity == "fail"
    ]
    return _GAP_FILL_PROMPT.format(
        fail_list="\n".join(f"- {line}" for line in fail_lines),
        markdown=markdown[:60_000],
    )


_DEAL_STRUCTURE_LABEL = {
    "stock_purchase": "Stock Purchase Agreement",
    "asset_purchase": "Asset Purchase Agreement",
    "merger": "Merger Agreement",
    "reverse_triangular_merger": "Merger Agreement (Reverse Triangular)",
}


USER_PROMPT_TEMPLATE = """## SPA / M&A Drafting Task

### Parties
- **Buyer**: {buyer}
- **Seller**: {seller}
- **Target Company**: {target_company}
- **Our role**: {our_role}

### Deal Structure
- **Type**: {deal_structure}
- **Price Structure**: {price_structure}

### Price (user-provided; blanks → [TBD])
- Enterprise Value: {ev}
- Cash at Closing: {cash_closing}
- Stock Consideration: {stock_pct}
- Earnout Max: {earnout}

### Indemnification
- Cap (% of price): {indemnity_cap_pct_of_price}%
- Basket: ${indemnity_basket_usd_mm}M
- Survival (general R&W): {indemnity_survival_months} months

### Closing Conditions
- HSR: {hsr}
- CFIUS: {cfius}
- SAMR (China antitrust): {samr}
- MAC clause: {mac}
- Interim period: {interim_period_months} months

### Post-Closing Covenants
- Non-compete: {non_compete_months} months
- Non-solicit: {non_solicit_months} months

### Governance
- Governing Law: {governing_law}
- Forum: {dispute_forum}

### Today
{today}

### Extra Context

{extra_context}

## Task

按系统提示的 13-节 + 风险提示（≥6）+ Checklist 输出完整 SPA / APA / Merger Agreement markdown 草案 (skeleton).
直接以 `# {deal_structure_label} — {target_company} ({seller} → {buyer})` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DraftSPAService(ReportService):
    slug = "draft-spa"
    display_name = "Draft SPA / M&A Agreement"
    description = (
        "起草 Stock Purchase Agreement / Asset Purchase Agreement / Merger Agreement "
        "草案 (skeleton)：从结构化参数（双方/标的/价格结构/赔偿 cap-basket-survival/"
        "监管 filing/MAC/non-compete）生成 13 节 markdown + .docx，含 Fundamentals vs "
        "General R&W 区分、≥6 商业风险提示。SPA 实际 100+ 页，本草案只是骨架。"
    )
    chat_tool_name = "draft_spa_agreement"
    chat_tool_description = (
        "Draft an SPA / APA / Merger Agreement skeleton from structured deal "
        "parameters (parties, deal structure, price + closing adjustments, "
        "indemnity cap-basket-survival, regulatory filings, MAC clause, "
        "non-compete). Produces a 13-section markdown + .docx with "
        "Fundamentals vs General R&W split, indemnification three-tuple "
        "(cap/basket/survival), and ≥6 commercial-risk callouts. Output is "
        "a SKELETON — actual SPAs run 100+ pages and require M&A counsel. "
        "~80-120s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "buyer": {"type": "string"},
            "seller": {"type": "string"},
            "target_company": {"type": "string"},
            "our_role": {"type": "string", "enum": ["buyer", "seller"]},
            "deal_structure": {
                "type": "string",
                "enum": list(_DEAL_STRUCTURE),
                "default": "stock_purchase",
            },
            "price_structure": {
                "type": "string",
                "enum": list(_PRICE_STRUCTURE),
                "default": "all_cash",
            },
            "enterprise_value_usd_mm": {"type": "number"},
            "cash_at_closing_usd_mm": {"type": "number"},
            "stock_consideration_pct": {"type": "number", "minimum": 0, "maximum": 100},
            "earnout_max_usd_mm": {"type": "number"},
            "indemnity_cap_pct_of_price": {
                "type": "number",
                "default": 15.0,
                "minimum": 0,
                "maximum": 100,
            },
            "indemnity_basket_usd_mm": {
                "type": "number",
                "default": 0.5,
                "minimum": 0,
            },
            "indemnity_survival_months": {
                "type": "integer",
                "default": 18,
                "minimum": 6,
                "maximum": 72,
            },
            "requires_hsr_approval": {"type": "boolean", "default": False},
            "requires_cfius_review": {"type": "boolean", "default": False},
            "requires_china_antitrust": {"type": "boolean", "default": False},
            "has_mac_clause": {"type": "boolean", "default": True},
            "interim_period_months": {
                "type": "integer",
                "default": 6,
                "minimum": 1,
                "maximum": 24,
            },
            "non_compete_months": {
                "type": "integer",
                "default": 24,
                "minimum": 0,
                "maximum": 60,
            },
            "non_solicit_months": {
                "type": "integer",
                "default": 24,
                "minimum": 0,
                "maximum": 60,
            },
            "governing_law": {"type": "string", "default": "Delaware"},
            "dispute_forum": {"type": "string", "default": "Delaware Court of Chancery"},
            "extra_context": {"type": "string"},
        },
        "required": ["buyer", "seller", "target_company", "our_role"],
    }
    input_model = DraftSPAInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 100
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DraftSPAInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(
            f"Drafting SPA: {inp.buyer} ← {inp.target_company} (from {inp.seller}); "
            f"structure={inp.deal_structure}, our_role={inp.our_role}"
        )

        deal_structure_label = _DEAL_STRUCTURE_LABEL[inp.deal_structure]

        user_prompt = USER_PROMPT_TEMPLATE.format(
            buyer=inp.buyer,
            seller=inp.seller,
            target_company=inp.target_company,
            our_role=inp.our_role,
            deal_structure=inp.deal_structure,
            deal_structure_label=deal_structure_label,
            price_structure=inp.price_structure,
            ev=self._fmt_amount(inp.enterprise_value_usd_mm, "$", "M"),
            cash_closing=self._fmt_amount(inp.cash_at_closing_usd_mm, "$", "M"),
            stock_pct=self._fmt_amount(inp.stock_consideration_pct, "", "%"),
            earnout=self._fmt_amount(inp.earnout_max_usd_mm, "$", "M"),
            indemnity_cap_pct_of_price=inp.indemnity_cap_pct_of_price,
            indemnity_basket_usd_mm=inp.indemnity_basket_usd_mm,
            indemnity_survival_months=inp.indemnity_survival_months,
            hsr="yes" if inp.requires_hsr_approval else "no",
            cfius="yes" if inp.requires_cfius_review else "no",
            samr="yes" if inp.requires_china_antitrust else "no",
            mac="yes" if inp.has_mac_clause else "no",
            interim_period_months=inp.interim_period_months,
            non_compete_months=inp.non_compete_months,
            non_solicit_months=inp.non_solicit_months,
            governing_law=inp.governing_law,
            dispute_forum=inp.dispute_forum,
            today=today,
            extra_context=inp.extra_context or "(无)",
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=7000,
        )
        if not markdown or len(markdown) < 1500:
            raise RuntimeError(
                "LLM produced an empty or too-short SPA draft. "
                "Check that all required fields are populated."
            )

        # ── L0/L1 Schema validation + gap-fill retry ──────
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Save outputs (post-repair)
        slug = safe_slug(f"{inp.buyer}_{inp.seller}_{inp.target_company}") or "spa"
        md_filename = f"draft_spa_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown SPA saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{deal_structure_label} (Draft) — {inp.target_company}",
            subtitle=f"{inp.seller} → {inp.buyer} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"draft_spa_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp, ctx.task_id)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"SPA Draft — {inp.target_company} ({inp.seller} → {inp.buyer})",
                "buyer": inp.buyer,
                "seller": inp.seller,
                "target_company": inp.target_company,
                "our_role": inp.our_role,
                "deal_structure": inp.deal_structure,
                "schema_audit": schema_audit,
                "suggested_commands": suggested_commands,
            },
        )

    # ── Formatting helpers ─────────────────────────────────

    def _fmt_amount(self, val: float | None, prefix: str, suffix: str) -> str:
        if val is None:
            return "[TBD]"
        if float(val).is_integer():
            return f"{prefix}{int(val)}{suffix}"
        return f"{prefix}{val:.1f}{suffix}"

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        try:
            audit = validate_markdown(markdown, mode="draft_spa")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=8000,
                label="spa_gap_fill",
            )
            if len(patched) > 1500:
                audit2 = validate_markdown(patched, mode="draft_spa")
                ctx.log(
                    f"Post-gap-fill audit: FAIL={audit2.n_fail} "
                    f"WARN={audit2.n_warn} (was {audit.n_fail} fail)"
                )
                if audit2.n_fail < audit.n_fail:
                    schema_audit = audit_to_dict(audit2)
                    schema_audit["gap_fill_attempted"] = True
                    schema_audit["gap_fill_fail_before"] = audit.n_fail
                    schema_audit["gap_fill_fail_after"] = audit2.n_fail
                    return schema_audit, patched
                ctx.log("L1 gap-fill didn't reduce FAILs — keeping original")
            else:
                ctx.log("L1 gap-fill produced too-short output — keeping original")

            schema_audit = audit_to_dict(audit)
            schema_audit["gap_fill_attempted"] = True
            schema_audit["gap_fill_fail_before"] = audit.n_fail
            return schema_audit, markdown
        except Exception:
            logger.exception("Schema validation failed for task %s", ctx.task_id)
            return {"error": "validator_exception"}, markdown

    # ── Lifecycle handoff chips ─────────────────────────────

    def _build_suggested_commands(self, inp: DraftSPAInput, task_id: str) -> list[dict]:
        """After SPA draft → /legal review for an independent BD-risk pass.

        SPA conventions: buyer = 甲方, seller = 乙方.

        Embeds source_task_id={task_id} so /legal can pull the just-generated
        markdown directly — closing the lifecycle loop without making the
        user paste their draft again.
        """
        party_position = "甲方" if inp.our_role == "buyer" else "乙方"
        counterparty = inp.seller if inp.our_role == "buyer" else inp.buyer
        return [
            {
                "label": "Review SPA Risks",
                "command": (
                    f'/legal contract_type=spa party_position="{party_position}"'
                    f" source_task_id={task_id}"
                    f' counterparty="{counterparty}"'
                    f' project_name="{inp.target_company} ({inp.deal_structure})"'
                ),
                "slug": "legal-review",
            }
        ]
