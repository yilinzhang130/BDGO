"""
Draft License Agreement — generate a definitive license agreement draft.

Closes part of S6-02 (P1). Sister to /draft-ts (#102) and /draft-mta
(#110): same pattern, but for the **definitive license agreement** —
the post-TS contract that operationalizes a deal.

License agreements are 50+ pages in practice; this service produces a
13-section markdown skeleton with the most important commercial terms
filled in from structured input. Counsel still reviews before signing.

Key MTA-vs-License-vs-TS distinctions enforced here:
  - License has FULL royalty/milestone schedules (TS only has ranges)
  - License has Definitions section (TS doesn't need formal definitions)
  - License has Patent Prosecution & Enforcement (MTA / TS don't)
  - License has Effects of Termination (post-termination obligations)
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


_EXCLUSIVITY = ("exclusive", "co-exclusive", "non-exclusive")
_SUBLICENSE_RIGHT = ("none", "with_consent", "free")
_PATENT_PROSECUTION = ("licensor", "licensee", "joint")

_BINDING_NOTE = (
    "All license agreement provisions are BINDING upon execution. "
    "Section markers below are organizational, not binding-status flags "
    "(unlike TS which has binding/non-binding split)."
)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class FinancialTerms(BaseModel):
    """License-grade financial terms — must be more concrete than a TS."""

    upfront_usd_mm: float | None = Field(None, description="Upfront cash payment, $M")
    equity_pct: float | None = Field(None, description="Equity stake taken, %")
    dev_milestones: list[str] | None = Field(
        None,
        description=(
            "Dev milestones as e.g. ['IND $5M', 'Phase 2 entry $20M', "
            "'NDA submission $50M']. Free-form per-milestone strings."
        ),
    )
    sales_milestones: list[str] | None = Field(
        None,
        description=("Sales milestones e.g. ['First $100M sales $25M', '$500M sales $75M']."),
    )
    royalty_tiered: list[str] | None = Field(
        None,
        description=("Tiered royalties e.g. ['<$100M: 8%', '$100M-500M: 12%', '>$500M: 15%']."),
    )


class DraftLicenseInput(BaseModel):
    # Parties
    licensor: str = Field(..., description="授权方 — granting rights")
    licensee: str = Field(..., description="被授权方 — receiving rights")
    our_role: Literal["licensor", "licensee"] = Field(..., description="我方角色")

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

    # License scope
    field_of_use: str = Field(..., description="e.g. 'Oncology', 'NSCLC monotherapy'")
    territory: str = Field("Worldwide", description="License territory")
    exclusivity: Literal["exclusive", "co-exclusive", "non-exclusive"] = "exclusive"
    sublicense_right: Literal["none", "with_consent", "free"] = Field(
        "with_consent",
        description=(
            "'with_consent' = sublicense allowed but Licensor consent required (default); "
            "'free' = sublicense allowed without consent; 'none' = no sublicense rights."
        ),
    )

    # Financial
    financial_terms: FinancialTerms = Field(default_factory=FinancialTerms)

    # IP / Patent
    patent_prosecution_lead: Literal["licensor", "licensee", "joint"] = "licensor"
    enforcement_lead: Literal["licensor", "licensee", "joint"] = "licensor"

    # Term & misc
    term_basis: Literal["last-to-expire-patent", "fixed-term", "indefinite"] = (
        "last-to-expire-patent"
    )
    fixed_term_years: int | None = Field(
        None, ge=1, le=30, description="Only used if term_basis='fixed-term'"
    )
    royalty_term_years_post_first_sale: int = Field(
        10, ge=5, le=20, description="Royalty obligation tail after first commercial sale"
    )
    governing_law: str = "Hong Kong"
    dispute_forum: str = "HKIAC"

    # Free-form context
    extra_context: str | None = None


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 平台的资深 BD 法务起草师，服务 biotech 跨境交易。任务：根据**结构化的 deal 参数**起草一份**可作为讨论起点**的 License Agreement（正式授权协议）markdown 草案。

## 硬规则

1. **这是 draft，不是法律意见**：文档开头必须含**显著的免责声明**（"Not legal advice; counsel review required before signing"），中英双语。
2. **License 全节 binding** — 与 TS 不同（TS 部分 binding 部分 non-binding），License Agreement 一旦签署所有条款 binding。文档不需要逐节标注 [BINDING]，但必须在开头明确"all provisions binding upon execution"。
3. **数字驱动**：
   - 财务条款必须列出具体数字 / 占位 `[TBD]`
   - 里程碑必须明确触发条件 + 金额
   - Royalty 必须 tiered（按销售额分档，不是 flat rate）
4. **Definitions 节必须含核心术语**：Affiliate / Licensed Product / Net Sales / Field / Territory / Effective Date / Phase / Sublicense — 缺一不可（Net Sales 定义不清是审计的常见盲点）
5. **Patent Prosecution & Enforcement 必须明确分工**：谁主导申请 / 续费 / 维护？谁主导诉讼？被告时如何分担？
6. **Effects of Termination 必须明确**：终止后哪些条款存续？已支付的 milestone 是否退还？sublicense 是否随之终止？survival period 多长？
7. **leverage 适配**：
   - `licensor` 视角 → 严格 diligence 量化 milestone / 完整 audit / royalty stacking 保护 / 严格 sublicense 控制
   - `licensee` 视角 → 灵活 diligence / sublicense free / royalty cap / wide sublicense
8. **不替代律师 / 不脱离用户输入**：未指定的不要默认加（如 ROFN / RoFR / 强排他扩展）
9. **风险提示节必须 ≥ 5 条 commercial-risk** — License 比 TS / MTA 复杂度高，5 条最低门槛：royalty stacking / diligence triggers / sublicense economics / IP indemnity scope / change-of-control trigger 等

## 输出结构（严格按此 13 节）

```
# License Agreement — {asset} ({licensor} → {licensee})

> ⚠️ **Not legal advice / 非法律意见** — This is a BD draft for discussion only. Counsel review is mandatory before any party signs.
>
> **生成日期**: {today}  ·  **我方角色**: {our_role}
>
> **All provisions BINDING upon execution.**

## 一、Parties / 当事方
- **Licensor / 授权方**: {licensor}
- **Licensee / 被授权方**: {licensee}

## 二、Definitions / 定义
（必含至少 8 个核心术语：Affiliate, Licensed Product, Net Sales, Field, Territory, Effective Date, Phase, Sublicense — 给出具体定义，不要"to be defined"）

## 三、License Grant / 许可授予
（明确：exclusivity / territory / field / 包含哪些权利 — develop / make / use / sell / sublicense / improvement license）

## 四、Sublicense / 转许可
（用户配置：with_consent / free / none。如 with_consent 需描述同意标准 + sublicensee 经济分成 + reps 传递）

## 五、Diligence Obligations / 勤勉义务
（CRE 量化 milestone：IND / Phase 1 / Phase 2 / Phase 3 / NDA / first commercial sale 各自时间 + remediation triggers）

## 六、Financial Terms / 财务条款
- **Upfront**: $X.XM (如 [TBD])
- **Equity**: X% (if any)
- **Dev Milestones**: 表格 — 每条触发条件 + 金额
- **Sales Milestones**: 表格 — 每档销售阈值 + 金额
- **Royalty**: tiered 表格 — 销售额区间 + 比率
- **Royalty Term**: {royalty_term_years_post_first_sale} 年自首次商业销售起

## 七、Royalty Reports & Audit / 销售报告与审计
（quarterly reports / audit window 3-5 年 / Licensor 每年 1 次 audit / 误差 > 5% 由 Licensee 承担费用）

## 八、Patent Prosecution & Enforcement / 专利申请与执行
（按用户配置 patent_prosecution_lead / enforcement_lead；分工 / 费用承担 / 诉讼控制权）

## 九、Improvements & New IP / 改进与新 IP
（Foreground IP 归属 / Improvements 是否自动 license back / Joint inventions 处理）

## 十、Confidentiality / 保密
（双向 / 期限 / 标准例外条款）

## 十一、Reps & Warranties + Indemnification / 陈述保证与赔偿
（Licensor reps: IP 净土 / no infringement / no encumbrance；Licensee reps: 资金 / 经营能力；indemnification scope + cap）

## 十二、Term & Termination + Effects / 期限、终止与终止效果
- **Term Basis**: {term_basis}
- **Termination Triggers**: material breach / insolvency / change of control / convenience
- **Effects of Termination**: licensee 是否保留 sublicense / 已付 milestone 是否退还 / survival 列表（保密 / IP / 责任 / 已发生 royalty）

## 十三、Governing Law & Dispute Resolution + Misc / 适用法律 + 杂项
- **Governing Law**: {governing_law}
- **Dispute Resolution**: arbitration in {dispute_forum}
- **Misc**: Notices / Assignment / Force Majeure / Entire Agreement / Severability

## 商业风险提示（≥ 5 条）

仅 for {our_role} 视角，不是法律意见：

1. **风险标题** — 描述（≤ 60 字）+ 缓解建议
2. ...
3. ...
4. ...
5. ...

## 签署前 Checklist
- [ ] 律师 review（含跨境税务 + IP 转让登记）
- [ ] CMC 团队确认 Field 范围与现有 license-out 不冲突
- [ ] BD 团队确认 financial 与内部 target 一致
- [ ] IP 团队确认无与 third-party license 冲突 + 续费安排
- [ ] 财务团队确认 royalty 计算方法 + audit 流程
- [ ] (其他视角化必要事项)

---

*BD Go 平台自动生成 — 该文档仅作为讨论起点，不构成法律意见*
```

## 写作风格

- 中英双语：节标题双语；条款主体中英文都列出最关键的
- 中性陈述，不夸张
- 用户没传值的字段写 `[TBD — recommend XXX based on industry norm]`
"""


_GAP_FILL_PROMPT = """以下是已生成的 License Agreement markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- "section_missing" → 按 13 节顺序插入缺失节
- "section_content"（缺关键词）→ 该节中补全（如 Definitions 节缺 "Net Sales"）
- 风险提示节必须 ≥ 5 条编号风险（License 比 TS / MTA 复杂）
- Definitions 节必须含 ≥ 8 个核心术语：Affiliate / Licensed Product / Net Sales / Field / Territory / Effective Date / Phase / Sublicense
- 不要新增未列出的章节，不要删除已有内容
- 保持双语风格 + 数字驱动（用户传入数字优先；空白用 [TBD]）
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


USER_PROMPT_TEMPLATE = """## License Agreement Drafting Task

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

### License Scope
- **Field of Use**: {field_of_use}
- **Territory**: {territory}
- **Exclusivity**: {exclusivity}
- **Sublicense Right**: {sublicense_right}

### Financial Terms (user-provided; blanks → [TBD])
- Upfront: {upfront}
- Equity: {equity}
- Dev Milestones: {dev_milestones}
- Sales Milestones: {sales_milestones}
- Royalty (tiered): {royalty_tiered}

### IP / Patent Roles
- **Patent Prosecution Lead**: {patent_prosecution_lead}
- **Enforcement Lead**: {enforcement_lead}

### Term
- **Term Basis**: {term_basis}
- **Fixed Term**: {fixed_term_years} years (if applicable)
- **Royalty Term**: {royalty_term_years_post_first_sale} years post first commercial sale

### Governance
- **Governing Law**: {governing_law}
- **Dispute Forum**: {dispute_forum}

### Today
{today}

### Extra Context

{extra_context}

## Task

按系统提示的 13-节 + 风险提示（≥5 条）+ Checklist 输出完整 License Agreement markdown 草案。
直接以 `# License Agreement — {asset_name} ({licensor} → {licensee})` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DraftLicenseService(ReportService):
    slug = "draft-license"
    display_name = "Draft License Agreement"
    description = (
        "起草 License Agreement 草案：从结构化 deal 参数（双方/资产/scope/"
        "财务条款 tiered royalty/milestones/patent prosecution）生成 13 节 markdown + "
        ".docx，全节 binding，含 Definitions 节 + 商业风险提示 ≥5 条 + 签署前 checklist。"
    )
    chat_tool_name = "draft_license_agreement"
    chat_tool_description = (
        "Draft a definitive License Agreement from structured deal parameters "
        "(parties, asset, license scope, tiered financial terms, patent "
        "prosecution roles, term basis). Produces a 13-section markdown + "
        ".docx with full Definitions section, tiered royalties, milestone "
        "schedules, and ≥5 commercial-risk callouts. Output is a draft for "
        "discussion — counsel review required before signing. ~60-90s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "licensor": {"type": "string"},
            "licensee": {"type": "string"},
            "our_role": {"type": "string", "enum": ["licensor", "licensee"]},
            "asset_name": {"type": "string"},
            "indication": {"type": "string"},
            "target": {"type": "string"},
            "modality": {"type": "string", "enum": MODALITY_VALUES, "default": "other"},
            "phase": {"type": "string", "enum": PHASE_VALUES},
            "field_of_use": {"type": "string"},
            "territory": {"type": "string", "default": "Worldwide"},
            "exclusivity": {
                "type": "string",
                "enum": list(_EXCLUSIVITY),
                "default": "exclusive",
            },
            "sublicense_right": {
                "type": "string",
                "enum": list(_SUBLICENSE_RIGHT),
                "default": "with_consent",
            },
            "financial_terms": {
                "type": "object",
                "properties": {
                    "upfront_usd_mm": {"type": "number"},
                    "equity_pct": {"type": "number"},
                    "dev_milestones": {"type": "array", "items": {"type": "string"}},
                    "sales_milestones": {"type": "array", "items": {"type": "string"}},
                    "royalty_tiered": {"type": "array", "items": {"type": "string"}},
                },
            },
            "patent_prosecution_lead": {
                "type": "string",
                "enum": list(_PATENT_PROSECUTION),
                "default": "licensor",
            },
            "enforcement_lead": {
                "type": "string",
                "enum": list(_PATENT_PROSECUTION),
                "default": "licensor",
            },
            "term_basis": {
                "type": "string",
                "enum": ["last-to-expire-patent", "fixed-term", "indefinite"],
                "default": "last-to-expire-patent",
            },
            "fixed_term_years": {"type": "integer", "minimum": 1, "maximum": 30},
            "royalty_term_years_post_first_sale": {
                "type": "integer",
                "default": 10,
                "minimum": 5,
                "maximum": 20,
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
            "field_of_use",
        ],
    }
    input_model = DraftLicenseInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 75
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DraftLicenseInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(
            f"Drafting License: {inp.licensor} → {inp.licensee} for "
            f"{inp.asset_name} ({inp.indication}, {inp.phase}, our_role={inp.our_role})"
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
            field_of_use=inp.field_of_use,
            territory=inp.territory,
            exclusivity=inp.exclusivity,
            sublicense_right=inp.sublicense_right,
            upfront=self._fmt_amount(inp.financial_terms.upfront_usd_mm, "$", "M"),
            equity=self._fmt_amount(inp.financial_terms.equity_pct, "", "%"),
            dev_milestones=self._fmt_list(inp.financial_terms.dev_milestones),
            sales_milestones=self._fmt_list(inp.financial_terms.sales_milestones),
            royalty_tiered=self._fmt_list(inp.financial_terms.royalty_tiered),
            patent_prosecution_lead=inp.patent_prosecution_lead,
            enforcement_lead=inp.enforcement_lead,
            term_basis=inp.term_basis,
            fixed_term_years=inp.fixed_term_years if inp.fixed_term_years else "(N/A)",
            royalty_term_years_post_first_sale=inp.royalty_term_years_post_first_sale,
            governing_law=inp.governing_law,
            dispute_forum=inp.dispute_forum,
            today=today,
            extra_context=inp.extra_context or "(无)",
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=6000,
        )
        if not markdown or len(markdown) < 1000:
            raise RuntimeError(
                "LLM produced an empty or too-short License draft. "
                "Check that all required fields are populated."
            )

        # ── L0/L1 Schema validation + gap-fill retry ──────
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Save outputs (post-repair)
        slug = safe_slug(f"{inp.licensor}_{inp.licensee}_{inp.asset_name}") or "license"
        md_filename = f"draft_license_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown License saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"License Agreement (Draft) — {inp.asset_name}",
            subtitle=f"{inp.licensor} → {inp.licensee} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"draft_license_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp, ctx.task_id)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": (f"License Draft — {inp.licensor} → {inp.licensee} ({inp.asset_name})"),
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

    # ── Formatting helpers ─────────────────────────────────

    def _fmt_amount(self, val: float | None, prefix: str, suffix: str) -> str:
        if val is None:
            return "[TBD]"
        if float(val).is_integer():
            return f"{prefix}{int(val)}{suffix}"
        return f"{prefix}{val:.1f}{suffix}"

    def _fmt_list(self, items: list[str] | None) -> str:
        if not items:
            return "[TBD]"
        return "; ".join(items)

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        try:
            audit = validate_markdown(markdown, mode="draft_license")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=7000,
                label="license_gap_fill",
            )
            if len(patched) > 1000:
                audit2 = validate_markdown(patched, mode="draft_license")
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

    def _build_suggested_commands(self, inp: DraftLicenseInput, task_id: str) -> list[dict]:
        """After License draft → /legal review for an independent BD-risk pass.

        Embeds source_task_id={task_id} so /legal can pull the just-generated
        markdown directly without the user re-pasting their draft.
        """
        party_position = "乙方" if inp.our_role == "licensor" else "甲方"
        counterparty = inp.licensee if inp.our_role == "licensor" else inp.licensor
        chips: list[dict] = [
            {
                "label": "Review License Risks",
                "command": (
                    f'/legal contract_type=license party_position="{party_position}"'
                    f" source_task_id={task_id}"
                    f' counterparty="{counterparty}"'
                    f' project_name="{inp.asset_name} ({inp.indication})"'
                ),
                "slug": "legal-review",
            }
        ]
        # If we're the licensor (selling), prep for buyer DD on this license
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
