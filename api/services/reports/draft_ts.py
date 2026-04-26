"""
Draft Term Sheet — generate a BD term sheet draft from deal parameters.

Closes S5-01: previously /legal could only **review** existing contracts.
This service generates a NEW Term Sheet markdown + .docx from structured
inputs (parties, asset, financial terms, territory, exclusivity, etc.).

Output is explicitly a DRAFT — every section carries a comment about
binding-vs-non-binding status and where the term sits relative to
industry norms. The doc opens with a hard disclaimer that counsel
review is mandatory before signing.

Sister to /legal (LegalReviewService): /legal reviews; /draft-ts drafts.
Future PRs will add /draft-mta, /draft-license, /draft-codev, /draft-spa
following the same pattern (one focused service per contract type).
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from pydantic import BaseModel, Field

from services.document import docx_builder
from services.enums import MODALITY_VALUES, PHASE_VALUES
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


_TERRITORIES = (
    "Greater China",
    "China only",
    "Asia ex-Japan",
    "Asia inc-Japan",
    "ex-US",
    "ex-China",
    "US only",
    "EU only",
    "US + EU",
    "Worldwide",
    "Custom",
)

_EXCLUSIVITY = ("exclusive", "co-exclusive", "non-exclusive")

_GOVERNING_LAWS = (
    "Hong Kong",
    "New York",
    "England & Wales",
    "Singapore",
    "Delaware",
    "California",
    "Custom",
)

_DISPUTE_FORA = ("HKIAC", "SIAC", "ICC", "JAMS", "AAA", "Custom")

# Standard binding-vs-non-binding map for a TS — these sections are
# typically binding even in a non-binding TS overall.
_BINDING_SECTIONS = (
    "Confidentiality",
    "Exclusivity / No-Shop",
    "Break-up Fee",
    "Costs / Expense Allocation",
    "Governing Law",
    "Dispute Resolution",
    "Term & Termination of TS",
)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class FinancialTerms(BaseModel):
    """Optional structured financial terms. Anything left blank renders
    as `[TBD — to be negotiated]` in the draft, with a comparable anchor."""

    upfront_usd_mm: float | None = Field(None, description="Upfront cash payment, $M")
    equity_pct: float | None = Field(None, description="Equity stake taken, %")
    dev_milestones_total_usd_mm: float | None = Field(
        None, description="Total dev milestone payments, $M"
    )
    sales_milestones_total_usd_mm: float | None = Field(
        None, description="Total sales milestone payments, $M"
    )
    royalty_low_pct: float | None = Field(None, description="Royalty range low, %")
    royalty_high_pct: float | None = Field(None, description="Royalty range high, %")
    deal_total_anchor_usd_mm: float | None = Field(
        None, description="Total deal value anchor (BD headline), $M"
    )


class DraftTSInput(BaseModel):
    # Parties
    licensor: str = Field(..., description="授权方 / 卖方 — the party granting rights.")
    licensee: str = Field(..., description="被授权方 / 买方 — the party receiving rights.")
    our_role: Literal["licensor", "licensee"] = Field(
        ..., description="我方在这笔交易中的角色，影响 leverage 描述偏向。"
    )

    # Asset
    asset_name: str
    indication: str
    target: str | None = None
    modality: Literal[
        "small_molecule",
        "biologic_antibody",
        "adc",
        "bispecific",
        "cell_gene_therapy",
        "nucleic_acid_rna",
        "protac",
        "radioligand",
        "other",
    ] = "other"
    phase: Literal[
        "Preclinical",
        "Phase 1",
        "Phase 1/2",
        "Phase 2",
        "Phase 2/3",
        "Phase 3",
        "NDA/BLA",
        "Approved",
    ]

    # Deal scope
    territory: str = Field("Worldwide", description="Free text or one of preset territories.")
    field_of_use: str = Field(
        "All therapeutic uses", description="e.g. 'Oncology only', 'All therapeutic uses'"
    )
    exclusivity: Literal["exclusive", "co-exclusive", "non-exclusive"] = "exclusive"
    sublicense_allowed: bool = True

    # Financial
    financial_terms: FinancialTerms = Field(default_factory=FinancialTerms)

    # Term & misc
    term_years: int = Field(15, ge=1, le=30, description="Default 15 — common for license deals.")
    no_shop_days: int = Field(60, ge=0, le=180, description="Exclusivity / no-shop period in days.")
    governing_law: str = "Hong Kong"
    dispute_forum: str = "HKIAC"

    # Free-form context
    extra_context: str | None = Field(
        None,
        description=(
            "Anything special: prior CDA terms, comparable deals, party preferences, "
            "regulatory wrinkles (orphan / RMAT / fast track), cross-border tax structure."
        ),
    )


# ─────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 平台的资深 BD 法务起草师，服务 biotech 跨境交易。任务：根据**结构化的 deal 参数**起草一份**可作为讨论起点**的 Term Sheet（TS）markdown 草案。

## 硬规则

1. **这是 draft，不是法律意见**：文档开头必须含**显著的免责声明**（"Not legal advice; counsel review required before signing"），中英双语。
2. **每节标注 Binding / Non-Binding**：
   - **Binding**（即使整份 TS 是 non-binding 也通常 binding）：Confidentiality / Exclusivity (No-Shop) / Break-up Fee / Costs / Governing Law / Dispute Resolution / Term & Termination of TS
   - **Non-Binding**（核心商业条款，待 definitive agreement 确定）：Financial Terms / Diligence / Reps & Warranties / Other Commercial Terms
3. **数字驱动**：每个 financial term 都引用用户传入的数字（或 `[TBD — to be negotiated]` 当空白），并配 1 句 "comparable anchor"（对标行业类似阶段+modality 的典型范围，仅当能给出合理数字时；不能编造具体公司名/数字）。
4. **leverage 适配**：根据 our_role 调整语气：
   - `our_role=licensor`（我方授权出去）→ 财务条款写在 licensor-favorable 范围，diligence 严格，audit 权完整
   - `our_role=licensee`（我方授权进来）→ 财务条款写在 licensee-favorable 范围，diligence 灵活，sublicense 权完整
5. **不替代律师 / 不脱离用户输入**：不要新增用户没说的关键条款（如自动加 RoFN / RoFR）；如某条款用户没指定，写 `[Open — recommend XXX]` 让用户后续决定。
6. **风险提示节**必须列出 ≥ 3 个 commercial-risk 议题（不是法律风险）— 例如"royalty stacking"、"sublicense economics"、"insufficient diligence triggers"。

## 输出结构（严格按此 13 节）

```
# Term Sheet — {asset} ({licensor} → {licensee})

> ⚠️ **Not legal advice / 非法律意见** — This is a BD draft for discussion only. Counsel review is mandatory before any party signs.
>
> **生成日期**: {today}  ·  **我方角色**: {our_role}

## 一、Parties / 当事方
[Binding once signed]
- **Licensor / 授权方**: {licensor}
- **Licensee / 被授权方**: {licensee}

## 二、Subject Asset / 标的资产
[Non-Binding — defined in DA]
- **Asset / 资产**: {asset_name}
- **Indication / 适应症**: {indication}
- **Target / 靶点**: {target}
- **Modality**: {modality}
- **Stage / 阶段**: {phase}

## 三、Field of Use / 适用范围
[Non-Binding]

(描述 field 范围 + 是否含 line extensions / new indications)

## 四、Territory / 地域
[Non-Binding]

## 五、Exclusivity / 独占性
[Non-Binding]

(exclusive/co-exclusive/non-exclusive + sublicense 权细节)

## 六、Financial Terms / 财务条款
[Non-Binding — headline ranges only; definitive numbers in DA]

| Component | Amount | Comparable Anchor |
|---|---|---|
| Upfront | $X.XM | (e.g. 类似 Phase 2 ADC 交易典型 $30-100M upfront) |
| Equity | X% (if any) | ... |
| Dev Milestones (total) | $X-XM | ... |
| Sales Milestones (total) | $X-XM | ... |
| Royalty (Net Sales) | X-X% tiered | ... |
| **Deal Total Anchor** | $X-XB | (用户输入或推断) |

## 七、Diligence Obligations / 勤勉义务
[Non-Binding]

(CRE 量化里程碑 / 时限触发器)

## 八、IP Ownership & Improvements / IP 归属与改进
[Non-Binding]

(Background IP / Foreground IP / Joint IP 归属规则)

## 九、Reps & Warranties / 陈述与保证
[Non-Binding]

(标的资产 IP 净土 / 无 ongoing litigation / 监管文件真实性 等典型 reps)

## 十、Confidentiality / 保密
[**BINDING**]

(参考已签 CDA；TS 本身的保密期；披露豁免)

## 十一、Exclusivity / No-Shop / 排他期
[**BINDING**]

- **No-Shop Period**: {no_shop_days} days
- 适用范围: 限于本 TS 涉及资产 / 适用所有同类资产
- Break-up Fee: $XM (如适用)

## 十二、Term & Termination / 期限与终止
[**BINDING (TS-level)** + **Non-Binding (deal-level)**]

- TS Expiration / TS 失效: 90 天后或经双方 written extension
- Deal Term: {term_years} years from first commercial sale (or until last patent expires)

## 十三、Governing Law & Dispute Resolution / 适用法律与争议解决
[**BINDING**]

- **Governing Law**: {governing_law}
- **Dispute Resolution**: arbitration in {dispute_forum}, {dispute_forum} rules, English language, [seat city]

## 商业风险提示（≥ 3 条）

仅 for {our_role} 视角，不是法律意见：

1. **风险标题** — 描述（≤ 60 字）+ 缓解建议
2. ...
3. ...

## 签署前 Checklist
- [ ] 律师 review（含跨境税务）
- [ ] CMC 团队确认 Field of Use 不冲突现有 license-out
- [ ] BD 团队确认 financial range 与 internal target 一致
- [ ] IP 团队确认无与 third-party license 冲突
- [ ] (其他视角化必要事项)

---

*BD Go 平台自动生成 — 该文档仅作为讨论起点，不构成法律意见*
```

## 写作风格

- 中英双语：节标题双语；条款主体中英文都列出最关键的（financial terms 表格留英文）
- 不夸张：不要写"this is a fantastic deal" — 中性陈述
- 不重复用户输入：用户传了 upfront $50M 就写 $50M，不要再加"$50M (anchor: $30-100M)"，把 anchor 放 Comparable Anchor 列
- 当用户没传值：写 `[TBD — recommend negotiating in $30-50M range based on Phase 2 ADC comparables]`，给 actionable placeholder
"""


_GAP_FILL_PROMPT = """以下是已生成的 Term Sheet markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验的内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**（从第一行到最后一行）。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- 每条缺陷标注章节（section）和问题描述（message）；只修改相关章节
- "section_missing" → 在合理位置（按 13 节顺序）插入该节标题 + ≥150 字内容
- "section_content" → 在该节中补全缺失关键词（如 "BINDING" / "Royalty" / "律师"）
- "subsection_missing" → 在该 section 末尾追加 subsection
- 不要新增未列出的章节、不要删除已有内容、不要改标题格式
- 保持双语风格（中文为主，金额/术语英文）+ Binding/Non-Binding 标记
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


USER_PROMPT_TEMPLATE = """## TS Drafting Task

### Parties
- **Licensor**: {licensor}
- **Licensee**: {licensee}
- **Our role**: {our_role}

### Asset
- **Name**: {asset_name}
- **Indication**: {indication}
- **Target**: {target}
- **Modality**: {modality}
- **Phase**: {phase}

### Deal Scope
- **Territory**: {territory}
- **Field of Use**: {field_of_use}
- **Exclusivity**: {exclusivity}
- **Sublicense allowed**: {sublicense_allowed}

### Financial Terms (user-provided; blanks → recommend ranges)
- Upfront: {upfront}
- Equity: {equity}
- Dev Milestones (total): {dev_milestones}
- Sales Milestones (total): {sales_milestones}
- Royalty range: {royalty_range}
- Deal Total Anchor: {deal_total}

### Term & Other
- **Term**: {term_years} years
- **No-Shop**: {no_shop_days} days
- **Governing Law**: {governing_law}
- **Dispute Forum**: {dispute_forum}

### Today
{today}

### Extra Context

{extra_context}

## Task

按系统提示的 13-节 + 风险提示 + Checklist 输出完整 TS markdown 草案。直接以
`# Term Sheet — {asset_name} ({licensor} → {licensee})` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DraftTSService(ReportService):
    slug = "draft-ts"
    display_name = "Draft Term Sheet"
    description = (
        "起草 BD Term Sheet 草案：从结构化 deal 参数（双方/资产/territory/exclusivity/"
        "financial terms）生成 13 节 markdown + .docx，每节标 Binding / Non-Binding，"
        "含商业风险提示和签署前 checklist。Sister 服务 /legal（review）的 draft 端。"
    )
    chat_tool_name = "draft_term_sheet"
    chat_tool_description = (
        "Draft a BD Term Sheet from structured deal parameters (parties, asset, "
        "territory, exclusivity, financial terms). Produces a 13-section markdown "
        "+ .docx with Binding/Non-Binding labels, comparable anchors for financial "
        "terms, and commercial-risk callouts. Output is a draft for discussion — "
        "counsel review required before signing. ~40-60s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            # Parties
            "licensor": {"type": "string"},
            "licensee": {"type": "string"},
            "our_role": {"type": "string", "enum": ["licensor", "licensee"]},
            # Asset
            "asset_name": {"type": "string"},
            "indication": {"type": "string"},
            "target": {"type": "string"},
            "modality": {"type": "string", "enum": MODALITY_VALUES, "default": "other"},
            "phase": {"type": "string", "enum": PHASE_VALUES},
            # Scope
            "territory": {"type": "string", "default": "Worldwide"},
            "field_of_use": {"type": "string", "default": "All therapeutic uses"},
            "exclusivity": {
                "type": "string",
                "enum": list(_EXCLUSIVITY),
                "default": "exclusive",
            },
            "sublicense_allowed": {"type": "boolean", "default": True},
            # Financial — flat shape for ease of use from chat
            "financial_terms": {
                "type": "object",
                "properties": {
                    "upfront_usd_mm": {"type": "number"},
                    "equity_pct": {"type": "number"},
                    "dev_milestones_total_usd_mm": {"type": "number"},
                    "sales_milestones_total_usd_mm": {"type": "number"},
                    "royalty_low_pct": {"type": "number"},
                    "royalty_high_pct": {"type": "number"},
                    "deal_total_anchor_usd_mm": {"type": "number"},
                },
            },
            # Misc
            "term_years": {
                "type": "integer",
                "default": 15,
                "minimum": 1,
                "maximum": 30,
            },
            "no_shop_days": {
                "type": "integer",
                "default": 60,
                "minimum": 0,
                "maximum": 180,
            },
            "governing_law": {"type": "string", "default": "Hong Kong"},
            "dispute_forum": {"type": "string", "default": "HKIAC"},
            "extra_context": {"type": "string"},
        },
        "required": [
            "licensor",
            "licensee",
            "our_role",
            "asset_name",
            "indication",
            "phase",
        ],
    }
    input_model = DraftTSInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 50
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DraftTSInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(
            f"Drafting TS: {inp.licensor} → {inp.licensee} for {inp.asset_name} "
            f"({inp.indication}, {inp.phase}, {inp.modality}, our_role={inp.our_role})"
        )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            licensor=inp.licensor,
            licensee=inp.licensee,
            our_role=inp.our_role,
            asset_name=inp.asset_name,
            indication=inp.indication,
            target=inp.target or "(not specified)",
            modality=inp.modality,
            phase=inp.phase,
            territory=inp.territory,
            field_of_use=inp.field_of_use,
            exclusivity=inp.exclusivity,
            sublicense_allowed="yes" if inp.sublicense_allowed else "no",
            upfront=self._fmt_amount(inp.financial_terms.upfront_usd_mm, "$", "M"),
            equity=self._fmt_amount(inp.financial_terms.equity_pct, "", "%"),
            dev_milestones=self._fmt_amount(
                inp.financial_terms.dev_milestones_total_usd_mm, "$", "M"
            ),
            sales_milestones=self._fmt_amount(
                inp.financial_terms.sales_milestones_total_usd_mm, "$", "M"
            ),
            royalty_range=self._fmt_royalty_range(
                inp.financial_terms.royalty_low_pct, inp.financial_terms.royalty_high_pct
            ),
            deal_total=self._fmt_amount(inp.financial_terms.deal_total_anchor_usd_mm, "$", "M"),
            term_years=inp.term_years,
            no_shop_days=inp.no_shop_days,
            governing_law=inp.governing_law,
            dispute_forum=inp.dispute_forum,
            today=today,
            extra_context=inp.extra_context or "(无)",
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=5000,
        )
        if not markdown or len(markdown) < 800:
            raise RuntimeError(
                "LLM produced an empty or too-short TS draft. "
                "Check that all required fields are populated."
            )

        # ── L0/L1 Schema validation + gap-fill retry ──────
        # TS structural integrity matters: a missing section forces
        # downstream legal review to spot it. Run the validator and, if
        # there are FAILs, do one targeted patch pass.
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Save outputs (post-repair markdown if patch happened)
        slug = safe_slug(f"{inp.licensor}_{inp.licensee}_{inp.asset_name}") or "ts"
        md_filename = f"draft_ts_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown TS saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"Term Sheet (Draft) — {inp.asset_name}",
            subtitle=f"{inp.licensor} → {inp.licensee} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"draft_ts_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"TS Draft — {inp.licensor} → {inp.licensee} ({inp.asset_name})",
                "licensor": inp.licensor,
                "licensee": inp.licensee,
                "our_role": inp.our_role,
                "asset": inp.asset_name,
                "indication": inp.indication,
                "phase": inp.phase,
                "modality": inp.modality,
                "schema_audit": schema_audit,
                "suggested_commands": suggested_commands,
            },
        )

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        """Run schema validation; if FAILs, do one targeted gap-fill LLM pass.

        Returns (audit_dict, possibly_repaired_markdown). Never raises —
        validation failure must not block delivery (the draft is still
        useful even with structural issues; we just record them).
        """
        try:
            audit = validate_markdown(markdown, mode="draft_ts")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=6000,
                label="ts_gap_fill",
            )
            if len(patched) > 800:
                audit2 = validate_markdown(patched, mode="draft_ts")
                ctx.log(
                    f"Post-gap-fill audit: FAIL={audit2.n_fail} "
                    f"WARN={audit2.n_warn} (was {audit.n_fail} fail)"
                )
                # Only swap if the patch actually reduced FAILs
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

    # ── Formatting helpers ─────────────────────────────────

    def _fmt_amount(self, val: float | None, prefix: str, suffix: str) -> str:
        if val is None:
            return "[TBD]"
        # Render integers without trailing .0
        if float(val).is_integer():
            return f"{prefix}{int(val)}{suffix}"
        return f"{prefix}{val:.1f}{suffix}"

    def _fmt_royalty_range(self, low: float | None, high: float | None) -> str:
        if low is None and high is None:
            return "[TBD]"
        if low is not None and high is not None:
            return f"{low:.0f}-{high:.0f}% tiered"
        if low is not None:
            return f"≥ {low:.0f}%"
        return f"≤ {high:.0f}%"

    # ── Lifecycle handoff chips ─────────────────────────────

    def _build_suggested_commands(self, inp: DraftTSInput) -> list[dict]:
        """After drafting → most natural next step is sending to /legal review
        for an independent BD-risk pass before sharing with counterparty."""
        chips: list[dict] = [
            {
                "label": "Review TS Risks",
                "command": (
                    f"/legal contract_type=ts party_position="
                    f'"{"乙方" if inp.our_role == "licensor" else "甲方"}"'
                    f' counterparty="{inp.licensee if inp.our_role == "licensor" else inp.licensor}"'
                    f' project_name="{inp.asset_name} ({inp.indication})"'
                ),
                "slug": "legal-review",
            }
        ]

        # If the user is the licensor, after TS exchange the natural follow-up
        # is preparing for buyer DD (post-TS / pre-DA)
        if inp.our_role == "licensor":
            chips.append(
                {
                    "label": "Prepare Buyer DD Q&A",
                    "command": (
                        f'/dd company="{inp.licensor}" asset_name="{inp.asset_name}"'
                        f" perspective=seller"
                    ),
                    "slug": "dd-checklist",
                }
            )

        return chips
