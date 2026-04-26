"""
Data Room — generate a categorized BD data room document checklist.

Given an asset (company + name + modality + stage + indication), produces
an 8-category checklist of documents the seller should populate in the
data room before opening it to a buyer's DD team. Each item carries a
priority (🔴 必须 / 🟡 建议 / 🟢 可选), a one-line description, expected
file format, and stage/modality-specific notes.

The 8 categories are stable; what's inside each adapts to:
  - stage: Preclinical / P1 / P2 / P3 / NDA-BLA / Approved
    (more clinical evidence later, more discovery data earlier)
  - modality: small molecule vs biologic vs ADC vs cell/gene vs nucleic acid
    (CMC and IP package shape changes radically)
  - audience: mnc_buyer (default) / private_equity / internal_review
    (PE wants more financials, less CMC depth)
  - purpose: licensing / acquisition / partnership / dd_response

Output: .md + .docx with category tables.

Pipeline: single LLM call (template-heavy prompt, no web search needed).
~30-50s.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from pydantic import BaseModel, Field

from services.document import docx_builder
from services.enums import MODALITY_VALUES, PHASE_VALUES
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


_PURPOSES = ("licensing", "acquisition", "partnership", "dd_response")
_AUDIENCES = ("mnc_buyer", "private_equity", "internal_review")


# Category list is stable across stages/modalities — the items inside change.
_CATEGORIES = [
    ("clinical", "Clinical Data"),
    ("cmc", "CMC / Manufacturing"),
    ("nonclinical", "Nonclinical / Tox"),
    ("regulatory", "Regulatory"),
    ("ip", "IP & Exclusivity"),
    ("quality", "Quality / GMP"),
    ("commercial", "Commercial / Market"),
    ("corporate", "Corporate & Legal"),
]


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class DataRoomInput(BaseModel):
    company_name: str = Field(..., description="Asset owner / seller company")
    asset_name: str = Field(..., description="Specific asset (data rooms are asset-level)")
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
    ]
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
    indication: str | None = Field(
        None, description="Primary indication; affects clinical/regulatory specifics."
    )
    target: str | None = Field(None, description="Molecular target.")
    purpose: Literal["licensing", "acquisition", "partnership", "dd_response"] = "licensing"
    audience: Literal["mnc_buyer", "private_equity", "internal_review"] = "mnc_buyer"
    extra_context: str | None = Field(
        None, description="Anything special about this asset (e.g., FDA orphan, RMAT, PRV)."
    )


# ─────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 平台的资深数据室策划师，服务卖方 biotech 在 BD 交易中**搭建/审核 data room**。

任务：根据资产的 modality × stage × audience × purpose，生成一份**结构化的 8-类 数据室文件清单**。

## 硬规则

1. **8 个 category 固定**（顺序不变）：Clinical / CMC / Nonclinical / Regulatory / IP / Quality / Commercial / Corporate。每类必须出现，即使内容只有一两条。
2. **每条 item 必须含 4 个字段**：
   - **优先级**：🔴 必须 / 🟡 建议 / 🟢 可选
   - **文件名描述**（具体的 BD 行业用语，如 "CMC Module 3.2.S Drug Substance"，不要泛泛"CMC 文件"）
   - **格式**：PDF / Excel / DOCX / ZIP / Folder
   - **备注**：1 句话（为什么需要 / 是否仅当某条件成立 / 是否有 redacted 版本）
3. **数据驱动适配**：
   - **Modality 适配 CMC + IP**：small_molecule 重 impurity profile / 异构体；mAb 重 cell line / glyco；ADC 重 linker chemistry / DAR / payload；cell_gene_therapy 重 viral titer / 病毒载体 / potency assay；radioligand 重核素 supply chain / 半衰期 / 防护
   - **Stage 适配 Clinical + Regulatory**：Preclinical = no CSR，重 IND-enabling tox + GLP；P1 = early SAD/MAD + 早期 PK；P2 = early efficacy + biomarker；P3 = full safety database + integrated summary；Approved = + 商业 CMC + post-marketing
   - **Audience 适配深度**：mnc_buyer 完整 8 类；private_equity 减 CMC 深度，加 Commercial+Financial；internal_review 全部 + 分析师备注
   - **Purpose 适配**：licensing 重 IP + clinical；acquisition 加 corporate / cap table；partnership 重 clinical + regulatory；dd_response 加"已上传 vs 缺失"列
4. **不编造监管细节**：FDA / EMA / NMPA 文件类型保留英文官方名（IND, NDA, BLA, MAA, IB, CSR, CMC Module 3）
5. **不要超过 60 条 items**：太多变成噪音；80% 信息密度集中在 🔴 必须

## 输出结构（严格按此 markdown 模板）

```
# Data Room Checklist — {asset_name} ({company})

> **生成日期**: {today}  ·  **Modality**: {modality}  ·  **Stage**: {phase}  ·  **Purpose**: {purpose}
> **Audience**: {audience}  ·  **Indication**: {indication}

## 概览

简短一段（≤ 150 字）说明：本资产 stage+modality 下，data room 的核心 3 个 leverage 点（哪些文件是 deal 谈判关键，哪些只是 hygiene）。

## 一、Clinical Data
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | CSR for Pivotal Trial(s) | PDF | 含 protocol amendments + SAP |
| 🟡 | ... | ... | ... |
| 🟢 | ... | ... | ... |

## 二、CMC / Manufacturing
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | ... | ... | ... |

(以此类推 8 个 category)

## 数据室搭建 Tips（≤ 5 条）
- 文件夹结构按 category 命名，避免混合
- 命名 convention：`<category>_<item>_<version_or_date>.pdf`
- 敏感数据（公开 IP / 临床样本编号）准备 **redacted 版本** 给 stage-1 DD
- ...
- ...

## 已上传 vs 缺失（仅当 audience=internal_review 或 purpose=dd_response 时输出此节）
表格：item | 状态（✅ 已上传 / ⚠️ 缺失 / ❌ N/A） | 负责人 | 截止日
```

## 写作风格

- 中文行文，BD/CMC/regulatory 术语保留英文（CSR, IB, IND, CMC, DMF, CMC Module 3.2, COC, COA, MTP, PK, PD, ORR, AE, SAE）
- 表格紧凑，每个 item 一行
- 不堆砌 — 每个 category 5-10 条 🔴 必须 + 2-4 条 🟡 + 1-3 条 🟢
- 不重复（同一份文件不要同时出现在 Clinical 和 Regulatory 里 —— 选最贴切的 category）
"""


USER_PROMPT_TEMPLATE = """## 数据室搭建任务

- **公司 / 资产**: {company} / {asset}
- **Modality**: {modality}
- **Stage**: {phase}
- **Indication**: {indication}
- **Target**: {target}
- **Purpose**: {purpose}
- **Audience**: {audience}
- **今天**: {today}

## 补充上下文

{extra_context}

## 任务

按系统提示的 8-category 模板输出完整 markdown。直接以 `# Data Room Checklist — {asset} ({company})` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DataRoomService(ReportService):
    slug = "data-room"
    display_name = "Data Room Checklist"
    description = (
        "卖方搭建 BD 数据室文件清单：8-category × modality × stage × audience 自适应。"
        "输出每条 item 的优先级 (🔴/🟡/🟢) + 描述 + 格式 + 备注。"
    )
    chat_tool_name = "generate_data_room_checklist"
    chat_tool_description = (
        "Generate a categorized BD data room document checklist for a "
        "biotech asset. Adapts CMC depth to modality (small molecule / "
        "mAb / ADC / cell-gene therapy / etc.), clinical evidence depth "
        "to phase, document mix to audience (MNC buyer / PE / internal). "
        "Returns 8-category Word doc + .md, ~30-50s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "asset_name": {"type": "string"},
            "modality": {"type": "string", "enum": MODALITY_VALUES},
            "phase": {"type": "string", "enum": PHASE_VALUES},
            "indication": {"type": "string"},
            "target": {"type": "string"},
            "purpose": {
                "type": "string",
                "enum": list(_PURPOSES),
                "default": "licensing",
            },
            "audience": {
                "type": "string",
                "enum": list(_AUDIENCES),
                "default": "mnc_buyer",
            },
            "extra_context": {
                "type": "string",
                "description": "Special-status hints (FDA orphan, RMAT, PRV, fast track, etc.).",
            },
        },
        "required": ["company_name", "asset_name", "modality", "phase"],
    }
    input_model = DataRoomInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 40
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DataRoomInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(
            f"Generating data room checklist for {inp.company_name} / {inp.asset_name} "
            f"({inp.modality} · {inp.phase} · {inp.audience})…"
        )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            company=inp.company_name,
            asset=inp.asset_name,
            modality=inp.modality,
            phase=inp.phase,
            indication=inp.indication or "(未指定)",
            target=inp.target or "(未指定)",
            purpose=inp.purpose,
            audience=inp.audience,
            today=today,
            extra_context=inp.extra_context or "(无)",
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4500,
        )
        if not markdown or len(markdown) < 500:
            raise RuntimeError("LLM produced an empty or too-short data room checklist.")

        # Phase 2 — Save outputs
        slug = safe_slug(f"{inp.company_name}_{inp.asset_name}") or "asset"
        md_filename = f"data_room_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{inp.asset_name} — Data Room Checklist",
            subtitle=(
                f"{inp.company_name} · {inp.modality} · {inp.phase} · {inp.purpose} · {today}"
            ),
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"data_room_{slug}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.asset_name} Data Room Checklist",
                "company": inp.company_name,
                "asset": inp.asset_name,
                "modality": inp.modality,
                "phase": inp.phase,
                "purpose": inp.purpose,
                "audience": inp.audience,
                "suggested_commands": suggested_commands,
            },
        )

    # ── Lifecycle handoff chips ─────────────────────────────

    def _build_suggested_commands(self, inp: DataRoomInput) -> list[dict]:
        """After data room checklist → typical seller next steps:
        - Anticipate buyer questions (/dd perspective=seller) — strongest value
        - Draft NDA if not yet signed (purpose=licensing/partnership)
        """
        chips: list[dict] = []

        # Always offer seller-perspective DD prep — buyer will ask from the
        # data room contents
        chips.append(
            {
                "label": "Prepare Buyer DD Q&A",
                "command": (
                    f'/dd company="{inp.company_name}" asset_name="{inp.asset_name}"'
                    f" perspective=seller"
                ),
                "slug": "dd-checklist",
            }
        )

        # If purpose is licensing/partnership and no CDA likely yet → offer
        # to draft one (idempotent if already signed)
        if inp.purpose in ("licensing", "partnership"):
            project_name = inp.asset_name + (f" ({inp.indication})" if inp.indication else "")
            chips.append(
                {
                    "label": "Draft CDA / NDA",
                    "command": (
                        f'/legal contract_type=cda party_position="乙方"'
                        f' counterparty="<buyer name>"'
                        f' project_name="{project_name}"'
                    ),
                    "slug": "legal-review",
                }
            )

        return chips
