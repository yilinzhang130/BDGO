"""
Draft MTA — generate a Material Transfer Agreement draft from deal parameters.

Closes part of S6-01 (P1). Sister to /draft-ts (#102): same structural
pattern (13-section template, BINDING markers, comparable anchors,
commercial-risk callouts, signing checklist), but tailored for MTA's
specific risks — IP transfer chain, derivatives ownership, publication
control, "for any purpose" creep.

MTA is the most common contract in pharma BD — often signed before TS.
A poorly-drafted MTA can effectively transfer IP without compensation
(the "MTA-as-stealth-license" risk pattern), so the LLM is given strict
guidance on red-flag language to avoid.
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


_MATERIAL_TYPES = (
    "antibody",
    "cell_line",
    "compound",
    "vector",
    "plasmid",
    "tissue_sample",
    "rna_dna",
    "other",
)

_DERIVATIVES_OWNERSHIP = ("provider", "recipient", "joint", "negotiated")

# Sections that are typically Binding regardless of MTA "binding" status
_BINDING_SECTIONS = (
    "Confidentiality",
    "Term & Termination of MTA",
    "Material Return / Destruction",
    "Governing Law",
    "Dispute Resolution",
)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class DraftMTAInput(BaseModel):
    # Parties
    provider: str = Field(..., description="材料提供方 (Provider)")
    recipient: str = Field(..., description="材料接收方 (Recipient)")
    our_role: Literal["provider", "recipient"] = Field(
        ..., description="我方角色，影响 leverage 框架。"
    )

    # Material
    material_name: str = Field(..., description="标的材料名称（药代号 / 抗体名 / 细胞系名 等）")
    material_type: Literal[
        "antibody",
        "cell_line",
        "compound",
        "vector",
        "plasmid",
        "tissue_sample",
        "rna_dna",
        "other",
    ] = "other"
    material_description: str | None = Field(None, description="材料的简短科学描述（一两句）")

    # Research project
    project_title: str = Field(..., description="研究项目标题")
    project_scope: str = Field(
        ..., description="接收方将用此材料做什么 — 越具体越好（避免 'for any purpose' 创伤）"
    )

    # Derivatives & IP
    derivatives_ownership: Literal["provider", "recipient", "joint", "negotiated"] = Field(
        "negotiated",
        description=(
            "Material 衍生物 / 修饰物归属。'negotiated' 表示在 MTA 里"
            "明确写'未决定，由后续协议商定'，避免默认归 Provider。"
        ),
    )
    publication_review_days: int = Field(
        30,
        ge=0,
        le=180,
        description=(
            "Provider 审阅 Recipient 拟发表论文的窗口（天）。"
            "默认 30 — 行业惯例 30-60。超 90 是红旗。"
        ),
    )

    # Term & misc
    term_months: int = Field(12, ge=1, le=60, description="MTA 期限（月），默认 12")
    governing_law: str = "Hong Kong"
    dispute_forum: str = "HKIAC"

    # Free-form context
    extra_context: str | None = Field(
        None,
        description=(
            "其它特殊安排：是否含 ROFN / Option / 后续 license / 排他研究 / "
            "Provider 是否可使用 Recipient 数据 等。"
        ),
    )


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 平台的资深 BD/IP 法务起草师，服务 biotech 跨境交易。任务：根据**结构化的 deal 参数**起草一份**可作为讨论起点**的 Material Transfer Agreement（MTA）markdown 草案。

## 硬规则

1. **这是 draft，不是法律意见**：文档开头必须含**显著的免责声明**（"Not legal advice; counsel review required before signing"），中英双语。
2. **每节标注 Binding / Non-Binding**：MTA 通常整份 binding（不像 TS 多数 non-binding）。但 standard practice：
   - **Binding（自始 binding）**：所有节，包括 Confidentiality / Material Return / Term & Termination / Governing Law / Dispute Resolution / Reps & Warranties / Publication
   - 因此 MTA 标注大多为 [BINDING]，不必每节都标 Non-Binding
3. **MTA 红旗主动规避** — 这些表述让 MTA 实质等同 License，必须**避免使用**：
   - "for any purpose" / "为任何目的" → 用具体研究目的限定
   - "fully paid-up, worldwide, royalty-free, sublicensable" 完整四件套 → 拆开来写，仅给最小必要权限
   - "shall not enter into agreement with third parties" → 排他承诺要明确边界 + 期限
   - "Provider sole invention" 默认归 Provider → 区分 Background / Foreground / Joint
   - 披露至 "to enable reproduction in own research" → 限定到"完成本研究项目所必需"
4. **数据驱动**：每个时间 / 数量参数引用用户传入的数字（或 `[TBD]` 当空白），并在备注里点出"行业惯例"对照（30-60 天 publication review；5-10 年保密；3-6 月 ROFN/option 期）。
5. **leverage 适配**：根据 our_role 调整：
   - `our_role=provider`（我方提供材料）→ 衍生物归我方 / 严格 publication review / 强 audit / 限定使用范围
   - `our_role=recipient`（我方接收材料）→ 灵活的衍生物条款 / 短 publication review / 宽广研究范围
6. **不替代律师 / 不脱离用户输入**：用户没指定的不要默认加（如 ROFN / 强排他 / IP 转移）；如某条款用户没指定，写 `[Open — recommend XXX]`。
7. **风险提示节**必须列出 ≥ 3 个 commercial-risk 议题（不是法律风险）— 如 "MTA-as-stealth-license"、"derivative ownership ambiguity"、"publication veto power"。

## 输出结构（严格按此 12 节）

```
# Material Transfer Agreement — {material} ({provider} → {recipient})

> ⚠️ **Not legal advice / 非法律意见** — This is a BD draft for discussion only. Counsel review is mandatory before any party signs.
>
> **生成日期**: {today}  ·  **我方角色**: {our_role}  ·  **材料类型**: {material_type}

## 一、Parties / 当事方
[BINDING]
- **Provider / 材料提供方**: {provider}
- **Recipient / 材料接收方**: {recipient}

## 二、Material Definition / 标的材料定义
[BINDING]
- **Material**: {material_name}
- **Type**: {material_type}
- **Description**: {material_description}
- **Includes**: 明确是否包含 derivatives / modifications / progeny

## 三、Research Use / 研究用途
[BINDING]

(明确限定到 Research Project 范围；禁止 "for any purpose"；如需 commercial 使用，需要单独 license)

## 四、Disclosure / Know-How / 信息披露
[BINDING]

(限定到"完成本研究项目所必需"；不要"足以独立复现"水平 — 那是技术转移)

## 五、Derivatives & Modifications / 衍生物与修饰物
[BINDING]

(归属规则：Provider / Recipient / Joint / Negotiated 之一；明确 progeny vs derivative)

## 六、IP Ownership / IP 归属
[BINDING]
- **Background IP**: 各自保留
- **Foreground IP** (research-generated): 按用户配置归属
- **Joint Inventions**: 处理规则

## 七、Publications / 发表
[BINDING]
- **Review Window**: {publication_review_days} 天 (行业惯例 30-60)
- **Provider 权限**: 仅可要求删除其 Confidential Info 或推迟以保护 IP；不得无理拒绝

## 八、Confidentiality / 保密
[BINDING]

(双向；CI 定义；保密期限 5-10 年；标准例外条款 — public domain / independent dev / third party / required by law)

## 九、Material Return / Destruction / 材料返还/销毁
[BINDING]

(项目结束 / 终止后 30-90 天内返还或销毁；要求 Recipient 出具 certificate)

## 十、Term & Termination / 期限与终止
[BINDING]
- **Term**: {term_months} months
- **Termination**: 任何一方 30 天 written notice；存续条款（保密 / IP / 责任限制）

## 十一、Reps & Warranties + Limitations / 陈述保证与责任限制
[BINDING]

(Provider 不保证 Material 适合特定用途；Recipient 自担风险；间接损失豁免)

## 十二、Governing Law & Dispute Resolution / 适用法律与争议解决
[BINDING]

- **Governing Law**: {governing_law}
- **Dispute Resolution**: arbitration in {dispute_forum}, English language

## 商业风险提示（≥ 3 条）

仅 for {our_role} 视角，不是法律意见：

1. **风险标题** — 描述（≤ 60 字）+ 缓解建议
2. ...
3. ...

## 签署前 Checklist
- [ ] 律师 review（含 IP / FTO 影响）
- [ ] 研发团队确认 Material 范围
- [ ] (我方为 provider) 内部 IP 团队签 off Foreground 归属
- [ ] (我方为 recipient) 确认 publication veto 不影响 milestone
- [ ] (其他视角化必要事项)

---

*BD Go 平台自动生成 — 该文档仅作为讨论起点，不构成法律意见*
```

## 写作风格

- 中英双语：节标题双语；条款主体中英文都列出最关键的
- 不夸张：MTA 是中性技术协议
- 不重复用户输入：用户传了 publication_review_days=30 就写 30 天
- 当用户没传值：写 `[TBD — recommend XX based on industry norm of YY]`，给 actionable placeholder
"""


_GAP_FILL_PROMPT = """以下是已生成的 MTA markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- "section_missing" → 按 12 节顺序插入缺失节
- "section_content"（缺 BINDING）→ 该节必须含 [BINDING] 标记
- "section_content"（缺关键词）→ 该节中补全（如 derivatives 节缺归属规则）
- 不要新增未列出的章节，不要删除已有内容
- 避免使用 MTA 红旗短语（"for any purpose" / "fully paid-up" 完整四件套等）
- 保持 [BINDING] 标记，保持双语风格
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


USER_PROMPT_TEMPLATE = """## MTA Drafting Task

### Parties
- **Provider**: {provider}
- **Recipient**: {recipient}
- **Our role**: {our_role}

### Material
- **Name**: {material_name}
- **Type**: {material_type}
- **Description**: {material_description}

### Research Project
- **Title**: {project_title}
- **Scope**: {project_scope}

### Derivatives & Publications
- **Derivatives ownership**: {derivatives_ownership}
- **Publication review window**: {publication_review_days} days

### Term & Misc
- **Term**: {term_months} months
- **Governing Law**: {governing_law}
- **Dispute Forum**: {dispute_forum}

### Today
{today}

### Extra Context

{extra_context}

## Task

按系统提示的 12-节 + 风险提示 + Checklist 输出完整 MTA markdown 草案。直接以
`# Material Transfer Agreement — {material_name} ({provider} → {recipient})` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DraftMTAService(ReportService):
    slug = "draft-mta"
    display_name = "Draft MTA"
    description = (
        "起草 Material Transfer Agreement 草案：从结构化参数（双方/材料/研究项目/"
        "衍生物归属/发表窗口）生成 12 节 markdown + .docx，全节 [BINDING]，含 MTA 红旗"
        "主动规避（如 'for any purpose' 创伤）+ 商业风险提示 + 签署前 checklist。"
    )
    chat_tool_name = "draft_mta"
    chat_tool_description = (
        "Draft a BD Material Transfer Agreement from structured parameters "
        "(parties, material, research project, derivatives ownership, "
        "publication review). Produces a 12-section markdown + .docx with "
        "BINDING labels, MTA red-flag avoidance ('for any purpose', "
        "stealth-license language), and commercial-risk callouts. Output is "
        "a draft for discussion — counsel review required before signing. "
        "~40-60s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "recipient": {"type": "string"},
            "our_role": {"type": "string", "enum": ["provider", "recipient"]},
            "material_name": {"type": "string"},
            "material_type": {
                "type": "string",
                "enum": list(_MATERIAL_TYPES),
                "default": "other",
            },
            "material_description": {"type": "string"},
            "project_title": {"type": "string"},
            "project_scope": {"type": "string"},
            "derivatives_ownership": {
                "type": "string",
                "enum": list(_DERIVATIVES_OWNERSHIP),
                "default": "negotiated",
            },
            "publication_review_days": {
                "type": "integer",
                "default": 30,
                "minimum": 0,
                "maximum": 180,
            },
            "term_months": {
                "type": "integer",
                "default": 12,
                "minimum": 1,
                "maximum": 60,
            },
            "governing_law": {"type": "string", "default": "Hong Kong"},
            "dispute_forum": {"type": "string", "default": "HKIAC"},
            "extra_context": {"type": "string"},
        },
        "required": [
            "provider",
            "recipient",
            "our_role",
            "material_name",
            "project_title",
            "project_scope",
        ],
    }
    input_model = DraftMTAInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 45
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DraftMTAInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(
            f"Drafting MTA: {inp.provider} → {inp.recipient} for {inp.material_name} "
            f"({inp.material_type}, our_role={inp.our_role})"
        )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            provider=inp.provider,
            recipient=inp.recipient,
            our_role=inp.our_role,
            material_name=inp.material_name,
            material_type=inp.material_type,
            material_description=inp.material_description or "(not specified)",
            project_title=inp.project_title,
            project_scope=inp.project_scope,
            derivatives_ownership=inp.derivatives_ownership,
            publication_review_days=inp.publication_review_days,
            term_months=inp.term_months,
            governing_law=inp.governing_law,
            dispute_forum=inp.dispute_forum,
            today=today,
            extra_context=inp.extra_context or "(无)",
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4500,
        )
        if not markdown or len(markdown) < 800:
            raise RuntimeError(
                "LLM produced an empty or too-short MTA draft. "
                "Check that all required fields are populated."
            )

        # ── L0/L1 Schema validation + gap-fill retry ──────
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Save outputs (post-repair)
        slug = safe_slug(f"{inp.provider}_{inp.recipient}_{inp.material_name}") or "mta"
        md_filename = f"draft_mta_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown MTA saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"Material Transfer Agreement (Draft) — {inp.material_name}",
            subtitle=f"{inp.provider} → {inp.recipient} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"draft_mta_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp, ctx.task_id)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": (f"MTA Draft — {inp.provider} → {inp.recipient} ({inp.material_name})"),
                "provider": inp.provider,
                "recipient": inp.recipient,
                "our_role": inp.our_role,
                "material_name": inp.material_name,
                "material_type": inp.material_type,
                "schema_audit": schema_audit,
                "suggested_commands": suggested_commands,
            },
        )

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        """Schema audit; if FAIL>0, one targeted gap-fill LLM pass.

        Same shape as /draft-ts (#102) and the X-01..05 batch (#105-#109).
        Never raises — validation failure must not block delivery.
        """
        try:
            audit = validate_markdown(markdown, mode="draft_mta")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=5500,
                label="mta_gap_fill",
            )
            if len(patched) > 800:
                audit2 = validate_markdown(patched, mode="draft_mta")
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

    def _build_suggested_commands(self, inp: DraftMTAInput, task_id: str) -> list[dict]:
        """After drafting → most natural next step is /legal review for an
        independent BD-risk pass before sharing with counterparty.

        Embeds source_task_id={task_id} so /legal can pull the just-generated
        markdown directly without the user re-pasting their draft.
        """
        # party_position in /legal review depends on our_role
        # provider = 我方提供，对方接收 → 我方是 transferring party (typically 甲方)
        # recipient = 我方接收 → 我方是 receiving party (typically 乙方)
        party_position = "甲方" if inp.our_role == "provider" else "乙方"
        counterparty = inp.recipient if inp.our_role == "provider" else inp.provider

        chips: list[dict] = [
            {
                "label": "Review MTA Risks",
                "command": (
                    f'/legal contract_type=mta party_position="{party_position}"'
                    f" source_task_id={task_id}"
                    f' counterparty="{counterparty}"'
                    f' project_name="{inp.material_name} ({inp.project_title})"'
                ),
                "slug": "legal-review",
            }
        ]

        # If we're the provider, the natural follow-up in BD is the next
        # contract step (license / co-dev) once the research project completes
        if inp.our_role == "provider":
            chips.append(
                {
                    "label": "Plan License Negotiation",
                    "command": (
                        f'/draft-ts licensor="{inp.provider}" licensee="{inp.recipient}"'
                        f' our_role=licensor asset_name="{inp.material_name}"'
                        f' indication="(TBD — outcome of research project)"'
                        f' phase="Preclinical"'
                    ),
                    "slug": "draft-ts",
                }
            )

        return chips
