"""
Draft Co-Development Agreement — generate a co-development agreement draft.

Closes part of S6-03 (P1). Fourth in /draft-X family. Sister to
/draft-ts (#102), /draft-mta (#110), /draft-license (#111).

Key distinctions from License:
  - Symmetry — both parties contribute R&D, IP, costs (not just grantor→grantee)
  - Joint Steering Committee (JSC) with explicit voting + deadlock mechanism
  - Cost-sharing schedule (50/50 or weighted percentages)
  - Profit-sharing or split-territory commercialization
  - Joint IP ownership (typically)
  - Buyout / change-of-control mechanism is critical (more than License)
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


_COST_SPLIT_MODELS = ("50_50", "weighted_60_40", "weighted_70_30", "milestone_based", "custom")
_PROFIT_MODELS = ("equal", "weighted_by_cost", "split_territories", "tiered", "custom")
_DECISION_MAKING = ("jsc_consensus", "jsc_majority", "lead_party_decides", "phase_specific")


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class DraftCoDevInput(BaseModel):
    # Parties — both contribute (no licensor/licensee asymmetry)
    party_a: str = Field(..., description="Party A — typically the originator / IP owner")
    party_b: str = Field(..., description="Party B — co-development partner")
    our_role: Literal["party_a", "party_b"] = Field(..., description="我方在 deal 中的角色")

    # Asset
    program_name: str = Field(
        ..., description="Co-development program name (asset codename or platform)"
    )
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
    starting_phase: Literal[
        "Preclinical",
        "Phase 1",
        "Phase 1/2",
        "Phase 2",
        "Phase 2/3",
        "Phase 3",
        "NDA/BLA",
        "Approved",
    ] = "Preclinical"

    # Co-development structure
    cost_split_model: Literal[
        "50_50", "weighted_60_40", "weighted_70_30", "milestone_based", "custom"
    ] = Field(
        "50_50",
        description=(
            "How R&D costs are split. 50_50 most common; weighted favors one party; "
            "milestone_based ties splits to dev stages."
        ),
    )
    party_a_share_pct: int = Field(
        50, ge=0, le=100, description="Party A's cost share % (informational; aligns with model)"
    )
    profit_model: Literal["equal", "weighted_by_cost", "split_territories", "tiered", "custom"] = (
        Field(
            "weighted_by_cost",
            description=(
                "How profits / royalties split. weighted_by_cost = follow cost-share; "
                "split_territories = each party owns a region."
            ),
        )
    )

    # Decision-making
    decision_making: Literal[
        "jsc_consensus", "jsc_majority", "lead_party_decides", "phase_specific"
    ] = Field(
        "jsc_consensus",
        description=(
            "JSC voting model. jsc_consensus needs both; jsc_majority breaks ties via "
            "casting vote; lead_party_decides gives one party final authority."
        ),
    )
    deadlock_mechanism: Literal[
        "ceo_escalation", "buyout_option", "arbitration", "termination_right"
    ] = Field(
        "ceo_escalation",
        description=(
            "What happens when JSC can't agree. CEO escalation = elevate to senior; "
            "buyout = either side can buy the other out; arbitration = binding 3rd party."
        ),
    )

    # Territory / Commercialization
    commercialization_split: str = Field(
        "Joint worldwide",
        description=(
            "Free text. Examples: 'Joint worldwide', 'Party A owns ex-US, Party B owns US', "
            "'Party A leads US, Party B leads APAC'"
        ),
    )

    # Term & misc
    term_basis: Literal["last-to-expire-patent", "fixed-term", "indefinite"] = (
        "last-to-expire-patent"
    )
    fixed_term_years: int | None = Field(None, ge=1, le=30)
    governing_law: str = "Hong Kong"
    dispute_forum: str = "HKIAC"

    # Free-form context
    extra_context: str | None = None


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 平台的资深 BD 法务起草师，服务 biotech 跨境交易。任务：根据**结构化的 deal 参数**起草一份**可作为讨论起点**的 Co-Development Agreement（共同开发协议）markdown 草案。

## 硬规则

1. **这是 draft，不是法律意见**：文档开头必须含**显著的免责声明**（"Not legal advice; counsel review required before signing"），中英双语。
2. **Co-Dev 是对称结构** — 与 License（grantor→grantee 单向）不同，Co-Dev 双方都有 R&D 义务、IP 贡献、成本承担、收益权。语言上避免 licensor/licensee 措辞，用 Party A / Party B。
3. **JSC 必须明确**：组成（每方几人）/ 投票规则 / deadlock 机制 / phase-specific decisions（如 GTM 决策由谁定）。这是 Co-Dev 最常见纠纷源。
4. **Cost Sharing 必须含具体数字**：用户传入 cost_split_model + party_a_share_pct。如未指定明确写 [TBD]。包含 audit 权 + 季度对账机制。
5. **Profit / Revenue Split 必须明确**：与 cost split 关系（weighted_by_cost / equal / split_territories）。
6. **Territory / Commercialization 必须明确**：Joint worldwide vs split territories。如 split 必须明确各方 owns 哪个区域 + cross-border supply / pricing coordination。
7. **Buyout / Change-of-Control 必须明确**：当一方 acquired 时另一方有什么权利？fair-market-value 评估机制？这是 Co-Dev 比 License 更关键的条款。
8. **leverage 适配**：
   - `our_role=party_a` 视角 → IP contributor 偏重，veto over commercial decisions, 强 buyout right
   - `our_role=party_b` 视角 → development resource 偏重, veto over development plan changes, 灵活 buyout
9. **风险提示节必须 ≥ 5 条 commercial-risk** — Co-Dev 复杂度高于 License：JSC deadlock / cost overrun / partner change-of-control / IP attribution / commercialization conflict 等
10. **不替代律师 / 不脱离用户输入**：未指定的不要默认加（如 ROFN extensions / 强 exclusivity）

## 输出结构（严格按此 12 节）

```
# Co-Development Agreement — {program} ({party_a} × {party_b})

> ⚠️ **Not legal advice / 非法律意见** — This is a BD draft for discussion only. Counsel review is mandatory before any party signs.
>
> **生成日期**: {today}  ·  **我方角色**: {our_role}
>
> **All provisions BINDING upon execution.**

## 一、Parties / 当事方
- **Party A**: {party_a}
- **Party B**: {party_b}

## 二、Definitions / 定义
（必含至少 8 个核心术语：Affiliate / Co-Development Program / Joint Steering Committee / Background IP / Foreground IP / Joint IP / Field / Territory / Net Sales）

## 三、Joint Development Plan & Joint Steering Committee / 共同开发计划与 JSC
- **JSC Composition**: each party 3 reps (typical)
- **Voting**: 按用户配置 decision_making
- **Deadlock**: 按用户配置 deadlock_mechanism
- **Phase-Specific Decisions**: dev plan / clinical strategy / regulatory / commercialization 各由谁定
- **Meeting Cadence**: monthly during dev / quarterly post-launch

## 四、Cost Sharing & Funding / 成本分摊与资金安排
- **Cost Split Model**: {cost_split_model}
- **Split**: Party A {party_a_share_pct}% / Party B {party_b_share_pct}%
- **Budget Approval**: JSC must approve annual budget; >10% overrun triggers re-budget
- **Audit**: each party may audit annually with 30 days notice

## 五、IP Ownership & Improvements / IP 归属与改进
- **Background IP**: 各自保留, license to other party for Program use only
- **Foreground IP** (research-generated):
  - Joint inventions: jointly owned, free-license-back to each party for own field
  - Solo inventions: invent-and-own
- **Improvements**: each party's improvements to its own Background IP retained

## 六、Commercialization & Territory / 商业化与地域
- **Model**: {commercialization_split}
- **Cross-Border**: 如 split territories，明确 supply chain / pricing coordination / data sharing
- **Marketing & Brand**: who controls branding / promotional materials / lifecycle management

## 七、Diligence / 勤勉义务
- **Both parties** commit to CRE
- Quantitative milestones at JSC level (binding on whoever leads that workstream)
- Failure → JSC review; if not cured, the OTHER party can take over leadership

## 八、Confidentiality / 保密
（双向 / CI 定义 / 期限 5-10 年 / 标准例外条款）

## 九、Reps & Warranties + Indemnification / 陈述保证与赔偿
- Each party reps: IP ownership in its Background IP / non-infringement / authority to sign
- **Mutual indemnification**: each indemnifies for its own Background IP claims; joint liability for Foreground IP
- Cap at 1× total cumulative spend (typical)

## 十、Term & Termination + Effects / 期限、终止与终止效果
- **Term Basis**: {term_basis}
- **Termination Triggers**: material breach (90-day cure) / insolvency / change of control of either party
- **Effects of Termination**:
  - Joint IP: license back to non-breaching party for own use
  - Already-paid milestones: non-refundable
  - Survival: confidentiality / accrued obligations / IP / governing law

## 十一、Buyout / Change-of-Control / 收购选择权
- **Trigger Events**: change of control of either party / strategic divergence / 3-year stagnation
- **Buyout Mechanism**:
  - Either party may offer to buy the other out at fair-market-value (FMV)
  - FMV determined by independent investment-bank appraisal
  - 90-day right of first refusal for the other side to match
- **Continuation**: post-buyout, acquirer assumes all rights + obligations

## 十二、Governing Law & Dispute Resolution + Misc / 适用法律 + 杂项
- **Governing Law**: {governing_law}
- **Dispute Resolution**: arbitration in {dispute_forum}
- **Misc**: Notices / Assignment (with consent — strict in Co-Dev given partnership nature) / Force Majeure / Severability / Entire Agreement

## 商业风险提示（≥ 5 条）

仅 for {our_role} 视角，不是法律意见：

1. **JSC deadlock** — 长期决策卡住的成本和风险
2. **Cost overrun** — 实际预算超过 baseline 的处理机制
3. **Partner change-of-control** — 对方被 acquired 时我方权利
4. **IP attribution** — 联合发明的归属争议常见来源
5. **Commercialization conflict** — split-territory 时的 supply / pricing / brand 冲突
（继续添加）

## 签署前 Checklist
- [ ] 律师 review（含跨境税务 + 反垄断）
- [ ] BD 团队 + R&D 团队 + 财务团队 三方对齐
- [ ] IP 团队确认 Foreground IP 分配机制
- [ ] 内部 JSC 提名人选确认
- [ ] (其他视角化必要事项)

---

*BD Go 平台自动生成 — 该文档仅作为讨论起点，不构成法律意见*
```

## 写作风格

- 中英双语：节标题双语；条款主体中英文都列出最关键的
- 中性陈述；Co-Dev 是合作不是交易
- 用户没传值的字段写 `[TBD — recommend XXX based on industry norm]`
"""


_GAP_FILL_PROMPT = """以下是已生成的 Co-Development Agreement markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- "section_missing" → 按 12 节顺序插入缺失节
- "section_content"（缺关键词）→ 该节中补全（如 JSC 节缺 voting 规则）
- 风险提示节必须 ≥ 5 条编号风险（Co-Dev 复杂度高）
- JSC 节必须明确 voting + deadlock 机制
- Cost Sharing 必须有具体百分比或 [TBD]
- Buyout 节必须明确 trigger + FMV 机制
- 不要新增未列出的章节，不要删除已有内容
- 保持双语 + 数字驱动 + 对称语言（避免 licensor/licensee）
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


USER_PROMPT_TEMPLATE = """## Co-Development Agreement Drafting Task

### Parties
- **Party A**: {party_a}
- **Party B**: {party_b}
- **Our role**: {our_role}

### Asset / Program
- **Program**: {program_name}
- **Indication**: {indication}
- **Target**: {target}
- **Modality**: {modality}
- **Starting Phase**: {starting_phase}

### Cost Sharing
- **Model**: {cost_split_model}
- **Party A %**: {party_a_share_pct}
- **Party B %**: {party_b_share_pct}

### Profit & Decision Making
- **Profit Model**: {profit_model}
- **Decision Making**: {decision_making}
- **Deadlock Mechanism**: {deadlock_mechanism}

### Commercialization
- **Split**: {commercialization_split}

### Term
- **Term Basis**: {term_basis}
- **Fixed Term**: {fixed_term_years} years (if applicable)

### Governance
- **Governing Law**: {governing_law}
- **Dispute Forum**: {dispute_forum}

### Today
{today}

### Extra Context

{extra_context}

## Task

按系统提示的 12-节 + 风险提示（≥5）+ Checklist 输出完整 Co-Development Agreement markdown 草案。
直接以 `# Co-Development Agreement — {program_name} ({party_a} × {party_b})` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DraftCoDevService(ReportService):
    slug = "draft-codev"
    display_name = "Draft Co-Development Agreement"
    description = (
        "起草 Co-Development Agreement 草案：从结构化参数（双方/资产/cost split/JSC 投票/"
        "buyout 机制）生成 12 节 markdown + .docx，对称结构（不是 licensor-licensee），"
        "含 JSC + cost sharing + buyout 关键条款 + ≥5 商业风险提示 + 签署前 checklist。"
    )
    chat_tool_name = "draft_codev_agreement"
    chat_tool_description = (
        "Draft a Co-Development Agreement from structured deal parameters "
        "(parties, program, cost split model, JSC voting model, deadlock "
        "mechanism, commercialization territory split). Produces a 12-section "
        "markdown + .docx with symmetric party language, JSC structure, "
        "cost-sharing schedule, buyout/change-of-control mechanism, and ≥5 "
        "commercial-risk callouts. Output is a draft for discussion — counsel "
        "review required before signing. ~60-90s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "party_a": {"type": "string"},
            "party_b": {"type": "string"},
            "our_role": {"type": "string", "enum": ["party_a", "party_b"]},
            "program_name": {"type": "string"},
            "indication": {"type": "string"},
            "target": {"type": "string"},
            "modality": {"type": "string", "enum": MODALITY_VALUES, "default": "other"},
            "starting_phase": {
                "type": "string",
                "enum": PHASE_VALUES,
                "default": "Preclinical",
            },
            "cost_split_model": {
                "type": "string",
                "enum": list(_COST_SPLIT_MODELS),
                "default": "50_50",
            },
            "party_a_share_pct": {
                "type": "integer",
                "default": 50,
                "minimum": 0,
                "maximum": 100,
            },
            "profit_model": {
                "type": "string",
                "enum": list(_PROFIT_MODELS),
                "default": "weighted_by_cost",
            },
            "decision_making": {
                "type": "string",
                "enum": list(_DECISION_MAKING),
                "default": "jsc_consensus",
            },
            "deadlock_mechanism": {
                "type": "string",
                "enum": [
                    "ceo_escalation",
                    "buyout_option",
                    "arbitration",
                    "termination_right",
                ],
                "default": "ceo_escalation",
            },
            "commercialization_split": {"type": "string", "default": "Joint worldwide"},
            "term_basis": {
                "type": "string",
                "enum": ["last-to-expire-patent", "fixed-term", "indefinite"],
                "default": "last-to-expire-patent",
            },
            "fixed_term_years": {"type": "integer", "minimum": 1, "maximum": 30},
            "governing_law": {"type": "string", "default": "Hong Kong"},
            "dispute_forum": {"type": "string", "default": "HKIAC"},
            "extra_context": {"type": "string"},
        },
        "required": [
            "party_a",
            "party_b",
            "our_role",
            "program_name",
            "indication",
        ],
    }
    input_model = DraftCoDevInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 75
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DraftCoDevInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(
            f"Drafting CoDev: {inp.party_a} × {inp.party_b} for {inp.program_name} "
            f"(our_role={inp.our_role})"
        )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            party_a=inp.party_a,
            party_b=inp.party_b,
            our_role=inp.our_role,
            program_name=inp.program_name,
            indication=inp.indication,
            target=inp.target or "(not specified)",
            modality=inp.modality,
            starting_phase=inp.starting_phase,
            cost_split_model=inp.cost_split_model,
            party_a_share_pct=inp.party_a_share_pct,
            party_b_share_pct=100 - inp.party_a_share_pct,
            profit_model=inp.profit_model,
            decision_making=inp.decision_making,
            deadlock_mechanism=inp.deadlock_mechanism,
            commercialization_split=inp.commercialization_split,
            term_basis=inp.term_basis,
            fixed_term_years=inp.fixed_term_years if inp.fixed_term_years else "(N/A)",
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
                "LLM produced an empty or too-short Co-Dev draft. "
                "Check that all required fields are populated."
            )

        # ── L0/L1 Schema validation + gap-fill retry ──────
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Save outputs (post-repair)
        slug = safe_slug(f"{inp.party_a}_{inp.party_b}_{inp.program_name}") or "codev"
        md_filename = f"draft_codev_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown CoDev saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"Co-Development Agreement (Draft) — {inp.program_name}",
            subtitle=f"{inp.party_a} × {inp.party_b} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"draft_codev_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp, ctx.task_id)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": (f"CoDev Draft — {inp.party_a} × {inp.party_b} ({inp.program_name})"),
                "party_a": inp.party_a,
                "party_b": inp.party_b,
                "our_role": inp.our_role,
                "program_name": inp.program_name,
                "indication": inp.indication,
                "schema_audit": schema_audit,
                "suggested_commands": suggested_commands,
            },
        )

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        try:
            audit = validate_markdown(markdown, mode="draft_codev")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=7000,
                label="codev_gap_fill",
            )
            if len(patched) > 1000:
                audit2 = validate_markdown(patched, mode="draft_codev")
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

    def _build_suggested_commands(self, inp: DraftCoDevInput, task_id: str) -> list[dict]:
        """After CoDev draft → /legal review for an independent BD-risk pass.

        Co-Dev parties are symmetric — both are 甲方 / 乙方 depending on the
        contract template; we use 乙方 as a reasonable default for our_role=party_a
        (originator/IP owner).

        Embeds source_task_id={task_id} so /legal can pull the just-generated
        markdown directly without the user re-pasting their draft.
        """
        party_position = "乙方" if inp.our_role == "party_a" else "甲方"
        counterparty = inp.party_b if inp.our_role == "party_a" else inp.party_a
        return [
            {
                "label": "Review CoDev Risks",
                "command": (
                    f'/legal contract_type=co_dev party_position="{party_position}"'
                    f" source_task_id={task_id}"
                    f' counterparty="{counterparty}"'
                    f' project_name="{inp.program_name} ({inp.indication})"'
                ),
                "slug": "legal-review",
            }
        ]
