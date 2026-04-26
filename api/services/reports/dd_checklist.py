"""
DD Checklist — BD Due Diligence 问题清单生成器.

Stage-positioning 自适应生成 DD 尽调问卷。分析师一键生成可直接发给项目方的问题清单。

Pipeline:
  1. Resolve company → CRM 公司表 + 资产表
  2. 判定 positioning (FIC/BIC/Me-too/Generic) + stage (Preclin→Commercial)
  3. Tavily 3 次搜索：FDA guidance / competitor readout / SoC evolution
  4. LLM 分 3 次调用生成 8 章内容（按 stage-positioning 权重裁剪）
  5. 输出 .md + .docx
"""

from __future__ import annotations

import concurrent.futures
import datetime
import logging
import re
from typing import Literal

from crm_store import LIKE_ESCAPE, like_contains
from pydantic import BaseModel, Field

from services.document import docx_builder
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import format_web_results, safe_slug, search_and_deduplicate

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Positioning & Stage inference
# ─────────────────────────────────────────────────────────────

POSITIONING_VALUES = ["FIC", "BIC", "Me-too", "Generic"]
STAGE_VALUES = ["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Commercial"]


def _infer_positioning(diff_grade: str | None, diff_desc: str | None) -> str | None:
    """Map CRM 差异化分级/描述 → positioning."""
    blob = ((diff_grade or "") + " " + (diff_desc or "")).lower()
    if not blob.strip():
        return None
    # Keyword matching, order matters (generic before me-too)
    if any(kw in blob for kw in ["generic", "仿制", "一致性评价", "ande", "aNDA"]):
        return "Generic"
    if any(kw in blob for kw in ["first-in-class", "fic", "首创", "first in class"]):
        return "FIC"
    if any(kw in blob for kw in ["best-in-class", "bic", "同类最优", "best in class"]):
        return "BIC"
    if any(kw in blob for kw in ["me-too", "metoo", "同类", "me too"]):
        return "Me-too"
    return None


def _infer_stage(phase: str | None) -> str | None:
    """Map CRM 临床阶段 → normalized stage."""
    if not phase:
        return None
    p = phase.lower()
    if any(kw in p for kw in ["approved", "commercial", "market", "上市"]):
        return "Commercial"
    if any(kw in p for kw in ["phase 3", "phase iii", "phase3", "p3", "nda", "bla"]):
        return "Phase 3"
    if any(kw in p for kw in ["phase 2", "phase ii", "phase2", "p2"]):
        return "Phase 2"
    if any(kw in p for kw in ["phase 1", "phase i", "phase1", "p1"]):
        return "Phase 1"
    if any(kw in p for kw in ["preclin", "ind", "lead", "discovery", "临床前"]):
        return "Preclinical"
    return None


# ─────────────────────────────────────────────────────────────
# Stage × Positioning weight matrix
# ─────────────────────────────────────────────────────────────

# 每个章节在特定 stage+positioning 下的相对权重：
# "high" → 20-25 个问题；"medium" → 10-15；"low" → 5-8
# Key: (positioning, stage) → list of weights for Q1-Q8

_WEIGHT_MATRIX: dict[tuple[str, str], list[str]] = {
    # FIC
    ("FIC", "Preclinical"): ["high", "high", "medium", "low", "medium", "medium", "low", "medium"],
    ("FIC", "Phase 1"): ["high", "high", "medium", "medium", "medium", "medium", "low", "medium"],
    ("FIC", "Phase 2"): [
        "medium",
        "high",
        "medium",
        "high",
        "medium",
        "medium",
        "medium",
        "medium",
    ],
    ("FIC", "Phase 3"): ["medium", "medium", "medium", "high", "high", "medium", "high", "high"],
    ("FIC", "Commercial"): ["medium", "low", "medium", "medium", "medium", "high", "high", "high"],
    # BIC
    ("BIC", "Preclinical"): ["medium", "high", "medium", "low", "medium", "high", "low", "medium"],
    ("BIC", "Phase 1"): [
        "medium",
        "medium",
        "medium",
        "high",
        "medium",
        "high",
        "medium",
        "medium",
    ],
    ("BIC", "Phase 2"): [
        "medium",
        "medium",
        "medium",
        "high",
        "medium",
        "high",
        "medium",
        "medium",
    ],
    ("BIC", "Phase 3"): ["medium", "low", "medium", "high", "high", "high", "high", "high"],
    ("BIC", "Commercial"): ["medium", "low", "medium", "medium", "medium", "high", "high", "high"],
    # Me-too
    ("Me-too", "Preclinical"): [
        "medium",
        "low",
        "medium",
        "low",
        "medium",
        "high",
        "low",
        "medium",
    ],
    ("Me-too", "Phase 1"): [
        "medium",
        "low",
        "medium",
        "medium",
        "medium",
        "high",
        "medium",
        "medium",
    ],
    ("Me-too", "Phase 2"): ["medium", "low", "medium", "high", "high", "high", "high", "medium"],
    ("Me-too", "Phase 3"): ["medium", "low", "medium", "high", "high", "high", "high", "medium"],
    ("Me-too", "Commercial"): [
        "medium",
        "low",
        "medium",
        "medium",
        "medium",
        "high",
        "high",
        "high",
    ],
    # Generic
    ("Generic", "Preclinical"): ["low", "low", "high", "low", "high", "high", "medium", "medium"],
    ("Generic", "Phase 1"): ["low", "low", "high", "medium", "high", "high", "medium", "medium"],
    ("Generic", "Phase 2"): ["low", "low", "high", "medium", "high", "high", "high", "medium"],
    ("Generic", "Phase 3"): ["low", "low", "high", "medium", "high", "high", "high", "medium"],
    ("Generic", "Commercial"): ["low", "low", "high", "low", "high", "high", "high", "medium"],
}

_CHAPTER_TITLES = [
    "Q1. 公司与团队 (Company & Team)",
    "Q2. 科学与靶点 (Science & Target)",
    "Q3. CMC 与分子 (CMC & Molecule)",
    "Q4. 临床数据 (Clinical Data)",
    "Q5. 监管路径 (Regulatory)",
    "Q6. IP 与独占 (IP & Exclusivity)",
    "Q7. 市场与商业 (Market & Commercial)",
    "Q8. 交易结构 (Deal Structure)",
]

_WEIGHT_EMOJI = {"high": "🔴 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"}
_QUESTIONS_PER_WEIGHT = {"high": "20-25", "medium": "10-15", "low": "5-8"}


def _get_weights(positioning: str, stage: str) -> list[str]:
    return _WEIGHT_MATRIX.get((positioning, stage)) or ["medium"] * 8


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class DDChecklistInput(BaseModel):
    company: str = Field(..., description="Company to investigate (CRM 公司名 or free text)")
    asset_name: str | None = Field(
        None, description="Specific asset; blank = use CRM core pipeline"
    )
    positioning_hint: Literal["FIC", "BIC", "Me-too", "Generic"] | None = None
    stage_hint: Literal["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Commercial"] | None = None
    extra_context: str | None = Field(
        None, description="Anything the seller already disclosed or analyst already searched"
    )
    include_web_search: bool = True
    perspective: Literal["buyer", "seller"] = Field(
        "buyer",
        description=(
            "buyer = 买方视角，生成发给项目方的 DD 问题清单；"
            "seller = 卖方视角，预测买方会问什么 + 我方答复要点（用于会前准备）"
        ),
    )


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

_BUYER_SYSTEM_PROMPT = """你是 BD Go 平台的资深 Due Diligence 负责人，代表**买方（MNC / PE / Fund）**起草发给项目方 (biotech 卖方) 的尽调问题清单。

你的输出**直接发给项目方的 CSO / CMO / CFO**，所以：

硬规则：
1. **问题要specific**，带上资产的实际靶点/适应症/阶段，不能泛泛。反例："请介绍你们的专利"✗，正例："请提供 {靶点} composition-of-matter 专利的 priority date 和 remaining life (by jurisdiction)"✓
2. **问题要有明确期望答复类型** — 数字/表格/文件/陈述，括号里标明。例："(期望: 表格 + CSR 编号)"
3. **不暴露买方内部思路** — 不要在清单里写"我们怀疑他们"、"根据评估"等。只写问题。
4. **按 5 个等级排序问题**：🔴 HIGH (必答)、🟡 MEDIUM、🟢 LOW。每章三级都要有。
5. **中文问题 + 英文术语保留** (MoA, PK, PD, BE, CMC, IND, NDA, FTO, TAM 等)
6. **不要编造数据** — 除非 web search 或 CRM 中明确提供了竞品信息，否则不要引用具体竞品数据。宁可写"请提供 vs 可比竞品的对照数据"也不要捏造。
7. **数据稀疏直接说** — 标 `[CRM 数据缺失]`，不要填充"建议"为真数据
"""


_SELLER_SYSTEM_PROMPT = """你是 BD Go 平台的资深 BD/CSO 顾问，代表**卖方（biotech）**为即将到来的买方 DD 会议做准备。

你的任务：列出**买方最可能问的尖锐问题** + **我方应当准备的答复要点**，按章节组织。

硬规则：
1. **每个问题必须 specific** — 想象买方 BD/CSO 会怎么发起，带上资产的实际靶点/适应症/阶段/差异化分级。反例："他们会问你们的专利"✗，正例："买方 BD 会问：'{靶点} CoM 专利在 EU/US 的 remaining life，是否有 obviousness 风险？'"✓
2. **每条问题配一段答复要点** — 1-3 个 bullet：用 CRM 数据 / 公开数据 / 已披露事实回答；如果答不完整，明确写 `⚠️ 需进一步准备：XXX`，不要编造。
3. **按 3 级标记紧迫度**：🔴 HIGH (必答好) — 直接关系 deal go/no-go；🟡 MEDIUM — 影响估值或 term；🟢 LOW — 锦上添花。每章 3 级都要有。
4. **中文表述 + 英文术语保留** (MoA, PK, PD, BE, CMC, IND, NDA, FTO, TAM 等)
5. **答复要点不能 overpromise** — 没有 head-to-head 数据就老实说"目前无 head-to-head 数据，规划在 P2b 加入对照"，不要"基于内部分析显著优于"。
6. **数据稀疏直接说** — 标 `[CRM 数据缺失，需补充]`，不要编造。
7. **不替代法律 / 技术意见** — 答复要点是 BD 准备稿，会议前应由 CMC、临床、IP 团队最终审核。
"""


def _get_system_prompt(perspective: str) -> str:
    return _SELLER_SYSTEM_PROMPT if perspective == "seller" else _BUYER_SYSTEM_PROMPT


def _chapter_prompt(
    chapter_indices: list[int],  # 1-based
    chapter_titles: list[str],
    chapter_weights: list[str],
    asset_info: str,
    positioning: str,
    stage: str,
    extra_context: str,
    web_block: str,
    perspective: str = "buyer",
) -> str:
    """Build a prompt for a batch of chapters.

    `perspective` controls framing:
      - "buyer": output is a list of questions to ask the seller
      - "seller": output is anticipated buyer questions + our prepared answers
    """
    chapter_lines = []
    for idx in chapter_indices:
        title = chapter_titles[idx - 1]
        weight = chapter_weights[idx - 1]
        n_questions = _QUESTIONS_PER_WEIGHT[weight]
        chapter_lines.append(
            f"### 章节 {title}  [权重: {_WEIGHT_EMOJI[weight]} · 建议 {n_questions} 个问题]"
        )

    weight_guidance = {
        "FIC": "重点关注靶点验证 / MoA / translational biomarker；不要把 BIC 语言套进去",
        "BIC": "**每章必须含 'vs 对标 FIC' 的 specific 对比问题**。没有 head-to-head 数据也要追问为什么没做",
        "Me-too": "重点问 CMC / 市场 / 份额获取；科学章节简短带过",
        "Generic": "重点问 CMC 比对 / 杂质谱 / BE / 监管路径；临床章节聚焦 BE 而非 efficacy",
    }[positioning]

    output_template = _SELLER_OUTPUT_TEMPLATE if perspective == "seller" else _BUYER_OUTPUT_TEMPLATE
    framing = (
        "买方在 DD 会议上最可能问的问题 + 我方答复要点"
        if perspective == "seller"
        else "本章 DD 问题清单"
    )

    return f"""## 任务：为以下章节各写一份{framing}

本次的基本情况：
- **定位**: {positioning} — {weight_guidance}
- **阶段**: {stage}

### 资产信息
{asset_info}

### 已披露/已搜到的上下文
{extra_context or "(无)"}

### Tavily 网络搜索结果（生成 specific 内容时引用）
{web_block}

### 要写的章节

{chr(10).join(chapter_lines)}

### 输出格式（严格遵守）

对每个章节，按以下模板输出 markdown：

{output_template}

问题编号格式：`Q{{章号}}.{{序号}}`。例如 `Q2.1`, `Q2.2` ...。

**直接输出章节 markdown，不要前言或总结。**
"""


# ─────────────────────────────────────────────────────────────
# Output templates per perspective
# ─────────────────────────────────────────────────────────────


_BUYER_OUTPUT_TEMPLATE = """```
## {章节标题}

**本章DD重点**: (1-2 句针对本资产 stage+positioning 组合的说明)

### 🔴 HIGH — 必答

- **{问题编号}**: {问题}
  - *期望答复*: {数字/文件/表格/陈述}

- **{问题编号}**: ...

### 🟡 MEDIUM — 重要

- **{问题编号}**: ...
  - *期望答复*: ...

### 🟢 LOW — 补充

- **{问题编号}**: ...
```"""


_SELLER_OUTPUT_TEMPLATE = """```
## {章节标题}

**本章会议重点**: (1-2 句针对本资产 stage+positioning 组合，买方最可能死磕的方向)

### 🔴 HIGH — 必准备好

- **{问题编号}**: {买方可能问的问题}
  - *我方答复要点*:
    - {answer bullet 1（用 CRM/公开数据回答）}
    - {answer bullet 2}
    - {如有 gap，写 ⚠️ 需进一步准备：XXX}

- **{问题编号}**: ...

### 🟡 MEDIUM — 重要

- **{问题编号}**: {买方可能问的问题}
  - *我方答复要点*: ...

### 🟢 LOW — 锦上添花

- **{问题编号}**: ...
  - *我方答复要点*: ...
```"""


_BUYER_EXECUTIVE_SUMMARY_PROMPT = """## 任务：为本次 DD 写一份 Executive Summary

基于以下资产信息，写一段 150-200 字的 DD Executive Summary，格式：

```
## Executive Summary — 本次 DD 的核心关注点

根据 {{资产名}} 处于 **{{阶段}}** + **{{定位}}** 的组合，本次 DD 的三大核心关注：

1. **[核心风险 1 的 one-liner]** — (一句话说明为什么是本资产 stage+positioning 下的核心)
2. **[核心风险 2 的 one-liner]** — ...
3. **[核心风险 3 的 one-liner]** — ...

**建议 DD 节奏**: (1 句话，例如 "Round 1 聚焦 Q2-Q4 书面回复，Round 2 管理层会议，Round 3 现场/Data Room")
```

### 资产信息
{asset_info}

### 定位与阶段
- **定位**: {positioning}
- **阶段**: {stage}

### 项目方已披露/分析师已搜到的上下文
{extra_context_or_none}

直接输出 markdown，不要前言。
"""


_SELLER_EXECUTIVE_SUMMARY_PROMPT = """## 任务：为本次买方 DD 会议准备写一份 Executive Summary

基于以下资产信息，写一段 150-200 字的卖方 DD 会议准备 Executive Summary，格式：

```
## Executive Summary — 买方 DD 会议三大攻防焦点

根据 {{资产名}} 处于 **{{阶段}}** + **{{定位}}** 的组合，买方最可能死磕这三处：

1. **[攻防焦点 1 的 one-liner]** — (一句话说明买方为什么会盯这点 + 我方应对策略)
2. **[攻防焦点 2 的 one-liner]** — ...
3. **[攻防焦点 3 的 one-liner]** — ...

**建议会议准备**: (1 句话，例如 "提前发 P2 ORR + safety summary 给买方一周阅读，会上聚焦 Q4-Q5 临床数据问题")
```

### 资产信息
{asset_info}

### 定位与阶段
- **定位**: {positioning}
- **阶段**: {stage}

### 已披露/已搜到的上下文
{extra_context_or_none}

直接输出 markdown，不要前言。
"""


def _get_executive_summary_prompt(perspective: str) -> str:
    return (
        _SELLER_EXECUTIVE_SUMMARY_PROMPT
        if perspective == "seller"
        else _BUYER_EXECUTIVE_SUMMARY_PROMPT
    )


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DDChecklistService(ReportService):
    slug = "dd-checklist"
    display_name = "DD 问题清单 / 会议准备"
    description = (
        "针对单个 biotech 资产的**阶段-定位自适应**双向 DD 工具。"
        "perspective=buyer (默认)：买方视角生成发给项目方的 DD 问题清单；"
        "perspective=seller：卖方视角预测买方会问什么 + 我方答复要点（用于会前准备）。"
        "8 章节 (团队/科学/CMC/临床/监管/IP/市场/交易) × 4 定位 (FIC/BIC/Me-too/Generic) × 5 阶段权重矩阵。"
    )
    chat_tool_name = "generate_dd_checklist"
    chat_tool_description = (
        "Generate a BD Due Diligence document. Two perspectives: buyer (default) "
        "produces questions to ask the seller; seller produces anticipated buyer "
        "questions + our prepared answers for meeting prep. Stage × positioning "
        "adaptive over 8 chapters. Pulls CRM + optional Tavily search. Returns "
        "8-chapter Word doc (~60 entries, 120-180s)."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "Target company (CRM 公司名 e.g. 'Peg-Bio' or free text). Used to pull asset/stage/positioning from CRM.",
            },
            "asset_name": {
                "type": "string",
                "description": "Specific asset name. If omitted, uses the company's core pipeline from CRM.",
            },
            "positioning_hint": {
                "type": "string",
                "enum": ["FIC", "BIC", "Me-too", "Generic"],
                "description": "Override auto-inference from CRM 差异化分级. Use when CRM is sparse.",
            },
            "stage_hint": {
                "type": "string",
                "enum": ["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Commercial"],
                "description": "Override auto-inference from CRM 临床阶段.",
            },
            "extra_context": {
                "type": "string",
                "description": "Anything the seller already disclosed or analyst already learned (e.g. 'BP mentions exclusive China patent', 'Phase 2 readout expected Q3').",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Run Tavily searches for competitor readouts + regulatory guidance to make questions specific. Default true.",
                "default": True,
            },
            "perspective": {
                "type": "string",
                "enum": ["buyer", "seller"],
                "default": "buyer",
                "description": (
                    "buyer = 我方是 MNC/PE，生成发给项目方的 DD 问题清单 (default); "
                    "seller = 我方是 biotech，预测买方会问什么 + 我方答复要点 (for meeting prep)."
                ),
            },
        },
        "required": ["company"],
    }
    input_model = DDChecklistInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 180
    category = "research"
    field_rules: dict = {}

    # ── main run ────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DDChecklistInput(**params)
        today = datetime.date.today().isoformat()

        # Phase 1 — CRM resolution
        ctx.log(f"查 CRM: company='{inp.company}', asset='{inp.asset_name or '(any)'}'")
        company_row = self._query_company(ctx, inp.company)
        assets = self._query_assets(ctx, inp.company, inp.asset_name)

        if company_row:
            ctx.log(
                f"CRM 命中公司: {company_row.get('客户名称')} "
                f"({company_row.get('客户类型') or '-'}, {company_row.get('所处国家') or '-'})"
            )
        else:
            ctx.log(f"⚠️ CRM 未找到公司 '{inp.company}' — 将使用 extra_context / 泛化模板")

        if assets:
            ctx.log(f"CRM 资产命中 {len(assets)} 条")
            lead = assets[0]
        else:
            ctx.log("⚠️ CRM 无该公司资产 — 降级为公司层面 DD")
            lead = {}

        # Phase 2 — Stage & positioning decision
        # 保守默认：FIC 会让问题偏科学（不漏大风险），Phase 1 是中间值
        inferred_positioning = _infer_positioning(lead.get("差异化分级"), lead.get("差异化描述"))
        inferred_stage = _infer_stage(
            lead.get("临床阶段") or (company_row or {}).get("核心产品的阶段")
        )
        positioning = inp.positioning_hint or inferred_positioning or "FIC"
        stage = inp.stage_hint or inferred_stage or "Phase 1"

        inferred_note = ""
        if not inp.positioning_hint and inferred_positioning is None:
            inferred_note += (
                "（⚠️ positioning 未能从 CRM 推断，默认 FIC；如不准请用 positioning_hint 重跑）"
            )
        if not inp.stage_hint and inferred_stage is None:
            inferred_note += "（⚠️ stage 未能从 CRM 推断，默认 P1；如不准请用 stage_hint 重跑）"
        ctx.log(f"判定: positioning={positioning}, stage={stage} {inferred_note}")

        weights = _get_weights(positioning, stage)

        # Phase 3 — Tavily
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Tavily 3 次搜索 (guidance / competitor readout / SoC)...")
            web_results = self._run_web_searches(lead, positioning, stage)
            ctx.log(f"Tavily 返回 {len(web_results)} 条去重结果")
        else:
            ctx.log("Web search disabled")
        web_block = format_web_results(web_results, inp.include_web_search)

        # Phase 4 — Build asset info block
        asset_info = self._format_asset_info(inp.company, company_row, assets, lead)

        # Phase 5 — LLM: Executive Summary (perspective-aware)
        system_prompt = _get_system_prompt(inp.perspective)
        exec_summary_template = _get_executive_summary_prompt(inp.perspective)
        ctx.log(f"生成 Executive Summary ({inp.perspective})...")
        exec_summary = ctx.llm(
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": exec_summary_template.format(
                        asset_info=asset_info,
                        positioning=positioning,
                        stage=stage,
                        extra_context_or_none=inp.extra_context or "(无)",
                    ),
                }
            ],
            max_tokens=800,
        )

        # Phase 6 — LLM: 8 chapters in 3 batches (Q1-Q3, Q4-Q6, Q7-Q8)
        # Batches are independent (no running_summary chaining) — run in parallel.
        # MiniMax call_llm_sync creates its own httpx.Client per call (thread-safe).
        batches = [[1, 2, 3], [4, 5, 6], [7, 8]]

        def _run_batch(batch: list[int]) -> tuple[list[int], str]:
            prompt = _chapter_prompt(
                chapter_indices=batch,
                chapter_titles=_CHAPTER_TITLES,
                chapter_weights=weights,
                asset_info=asset_info,
                positioning=positioning,
                stage=stage,
                extra_context=inp.extra_context or "",
                web_block=web_block,
                perspective=inp.perspective,
            )
            batch_md = ctx.llm(
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3200,
            )
            return batch, batch_md

        chapter_texts: dict[int, str] = {}
        ctx.log(f"并发生成 3 批章节: {batches}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batches)) as pool:
            for batch, batch_md in pool.map(_run_batch, batches):
                for idx, chunk in self._split_chapters(batch_md, batch):
                    chapter_texts[idx] = chunk
                ctx.log(f"批 {batch} 完成 ({len(batch_md)} 字)")

        # Phase 7 — Assemble markdown (perspective-aware header)
        display_name = lead.get("资产名称") or (company_row or {}).get("客户名称") or inp.company
        is_seller = inp.perspective == "seller"
        title_label = "买方 DD 会议准备" if is_seller else "BD Due Diligence 问题清单"
        usage_note = (
            "本文档是**卖方会前准备稿**：每条「买方可能问」+「我方答复要点」。"
            "🔴 必准备好（go/no-go 关键）；🟡 重要（影响估值/term）；🟢 锦上添花。"
            "会前由 CMC / 临床 / IP 团队最终审核。"
            if is_seller
            else "本清单按买方 DD 关注优先级排序。标 🔴 的问题为本资产 stage + positioning 下的核心风险，必须在首轮 DD 内获得答复；🟡 重要；🟢 补充。请项目方以「问题编号 + 书面答复 + 附件索引」格式回复。"
        )
        header = (
            f"# {display_name} — {title_label}\n\n"
            f"> **生成日期**: {today}  |  **视角**: {inp.perspective}  |  **分析师**: BD Go\n"
            f"> **定位**: {positioning}  |  **阶段**: {stage}  |  **CRM 命中**: "
            f"{'✓ ' + (company_row.get('客户名称', '?')) if company_row else '✗ 未命中（使用泛化模板）'}\n\n"
            f"> **使用说明**: {usage_note}\n\n"
            "---\n\n"
        )

        body_chapters = []
        for idx in range(1, 9):
            if idx in chapter_texts:
                body_chapters.append(chapter_texts[idx].strip())
            else:
                body_chapters.append(
                    f"## {_CHAPTER_TITLES[idx - 1]}\n\n[章节生成失败，请重跑任务或联系管理员]"
                )

        markdown = header + exec_summary.strip() + "\n\n---\n\n" + "\n\n---\n\n".join(body_chapters)
        markdown += "\n\n---\n\n" + self._appendix_section()

        if len(markdown) < 500:
            raise RuntimeError("DD checklist generation produced empty output")

        # Phase 8 — Save (filename reflects perspective)
        slug = safe_slug(display_name) or "asset"
        prefix = "dd_meeting_prep" if inp.perspective == "seller" else "dd_checklist"
        md_name = f"{prefix}_{slug}_{today}.md"
        docx_name = f"{prefix}_{slug}_{today}.docx"

        ctx.save_file(md_name, markdown, format="md")
        ctx.log("Markdown 已保存")

        ctx.log("渲染 Word 文档...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{display_name} {title_label}",
            subtitle=f"{positioning} · {stage} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(docx_name, docx_bytes, format="docx")
        ctx.log("Word 已保存")

        suggested_commands = self._build_suggested_commands(inp, lead, stage)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{display_name} {title_label}",
                "company": inp.company,
                "asset": lead.get("资产名称") or inp.asset_name or "",
                "positioning": positioning,
                "stage": stage,
                "perspective": inp.perspective,
                "crm_hit_company": bool(company_row),
                "crm_hit_assets": len(assets),
                "web_results_count": len(web_results),
                "inferred_fallback": bool(inferred_note),
                "suggested_commands": suggested_commands,
            },
        )

    # ── BD lifecycle: post-DD next-step chips ───────────────
    def _build_suggested_commands(
        self, inp: DDChecklistInput, lead: dict, stage: str
    ) -> list[dict]:
        """After DD completes, suggest deal valuation tools if CRM has enough asset data."""
        asset_name = lead.get("资产名称") or inp.asset_name or ""
        if not asset_name:
            return []

        company = inp.company
        target = lead.get("靶点") or ""
        indication = lead.get("适应症") or ""
        modality = lead.get("技术平台类别") or ""

        commands: list[dict] = []

        if target and indication:
            evaluate_cmd = (
                f'/evaluate company_name="{company}" asset_name="{asset_name}"'
                f' target="{target}" indication="{indication}" phase="{stage}"'
            )
            commands.append(
                {"label": "Deal Evaluation", "command": evaluate_cmd, "slug": "deal-evaluator"}
            )

        if indication and modality:
            rnpv_cmd = (
                f'/rnpv company_name="{company}" asset_name="{asset_name}"'
                f' indication="{indication}" phase="{stage}" modality="{modality}"'
            )
            commands.append(
                {"label": "rNPV Valuation", "command": rnpv_cmd, "slug": "rnpv-valuation"}
            )

        return commands

    # ── CRM queries ─────────────────────────────────────────
    def _query_company(self, ctx: ReportContext, company: str) -> dict | None:
        rows = ctx.crm_query(
            f'SELECT "客户名称", "客户类型", "所处国家", "核心产品的阶段", '
            f'"主要核心pipeline的名字", "BD跟进优先级" '
            f'FROM "公司" WHERE "客户名称" ILIKE ? {LIKE_ESCAPE} LIMIT 1',
            (like_contains(company),),
        )
        return rows[0] if rows else None

    def _query_assets(self, ctx: ReportContext, company: str, asset_name: str | None) -> list[dict]:
        if asset_name:
            rows = ctx.crm_query(
                f'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
                f'"疾病领域", "适应症", "差异化分级", "差异化描述", "Q总分", "技术平台类别" '
                f'FROM "资产" WHERE "资产名称" ILIKE ? {LIKE_ESCAPE} AND "所属客户" ILIKE ? {LIKE_ESCAPE} LIMIT 10',
                (like_contains(asset_name), like_contains(company)),
            )
            if rows:
                return rows
        # Fallback: all assets of the company
        return ctx.crm_query(
            f'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
            f'"疾病领域", "适应症", "差异化分级", "差异化描述", "Q总分", "技术平台类别" '
            f'FROM "资产" WHERE "所属客户" ILIKE ? {LIKE_ESCAPE} LIMIT 10',
            (like_contains(company),),
        )

    # ── Web search ──────────────────────────────────────────
    def _run_web_searches(self, lead: dict, positioning: str, stage: str) -> list[dict]:
        target = lead.get("靶点") or ""
        indication = lead.get("适应症") or lead.get("疾病领域") or ""
        asset = lead.get("资产名称") or ""

        queries: list[str] = []
        if target and indication:
            queries.append(f"{target} {indication} FDA NMPA regulatory guidance 2025 2026")
        if target and stage not in ("Commercial", "Preclinical"):
            queries.append(f"{target} {stage} competitor clinical readout 2025 2026")
        if indication:
            queries.append(f"{indication} standard of care evolution 2025 2026")
        if asset and not queries:
            queries.append(f"{asset} biotech due diligence pipeline readout")

        return search_and_deduplicate(queries, max_results_per_query=3)

    # ── Formatting ──────────────────────────────────────────
    def _format_asset_info(
        self,
        user_company: str,
        company: dict | None,
        assets: list[dict],
        lead: dict,
    ) -> str:
        lines = [f"**用户输入的公司名**: {user_company}"]
        if company:
            lines.append(
                f"**CRM 公司**: {company.get('客户名称', '?')} | "
                f"{company.get('客户类型') or '-'} | "
                f"{company.get('所处国家') or '-'} | "
                f"核心阶段: {company.get('核心产品的阶段') or '-'} | "
                f"核心 pipeline: {company.get('主要核心pipeline的名字') or '-'}"
            )
        else:
            lines.append("**CRM 公司**: [未命中 — 使用用户输入]")

        if lead:
            lines.append(
                f"\n**核心资产** (取 CRM 第 1 条):\n"
                f"- 资产名: {lead.get('资产名称', '?')}\n"
                f"- 靶点: {lead.get('靶点') or '[未填写]'}\n"
                f"- MoA: {lead.get('作用机制(MOA)') or '[未填写]'}\n"
                f"- 临床阶段: {lead.get('临床阶段') or '[未填写]'}\n"
                f"- 疾病领域: {lead.get('疾病领域') or '[未填写]'}\n"
                f"- 适应症: {lead.get('适应症') or '[未填写]'}\n"
                f"- 差异化分级: {lead.get('差异化分级') or '[未填写]'}\n"
                f"- 差异化描述: {lead.get('差异化描述') or '[未填写]'}\n"
                f"- Q 总分: {lead.get('Q总分') or '-'}\n"
                f"- 技术平台类别: {lead.get('技术平台类别') or '-'}"
            )
        else:
            lines.append("\n**核心资产**: [CRM 无资产记录 — 将使用公司层面 DD + 泛化问题]")

        if len(assets) > 1:
            others = assets[1:5]
            lines.append(f"\n**其他资产** ({len(assets) - 1} 条):")
            for a in others:
                lines.append(
                    f"- {a.get('资产名称', '?')} | {a.get('靶点', '-')} | "
                    f"{a.get('临床阶段', '-')} | {a.get('适应症', '-')}"
                )

        return "\n".join(lines)

    def _split_chapters(self, batch_md: str, expected_indices: list[int]) -> list[tuple[int, str]]:
        """Split an LLM batch output into (chapter_index, chunk) pairs."""
        # Match headers like "## Q1." / "## Q2." etc.
        pattern = re.compile(r"^(##\s+Q(\d)\.[^\n]*)$", re.MULTILINE)
        matches = list(pattern.finditer(batch_md))
        if not matches:
            # Fallback: attribute whole blob to the first expected index
            return [(expected_indices[0], batch_md)]

        results: list[tuple[int, str]] = []
        for i, m in enumerate(matches):
            try:
                idx = int(m.group(2))
            except ValueError:
                continue
            if idx not in expected_indices:
                continue
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(batch_md)
            results.append((idx, batch_md[start:end].strip()))
        return results

    def _appendix_section(self) -> str:
        return """## 附录 A — 希望项目方准备的文件清单

- [ ] 最新版 Pitch Deck + 财务 Model
- [ ] 核心专利清单（申请号 / 授权号 / priority date / 剩余寿命 / 地域）
- [ ] 全部 clinical trial protocols + 已完成研究的 CSR
- [ ] IND / NDA submission 相关章节 (Modules 2-5)
- [ ] CMC: Drug Substance + Drug Product 工艺流程 + 稳定性数据
- [ ] 所有与监管机构的 meeting minutes（pre-IND / EOP1 / EOP2 / Type C 等）
- [ ] In-licensed / Out-licensed agreements 清单
- [ ] Cap table + 管理层 agreement 核心条款
- [ ] 近 12 月 pharmacovigilance database snapshot（若已进入临床）

## 附录 B — 建议 DD 节奏

| Round | 时间窗 | 内容 |
|-------|--------|------|
| Round 1 | T+1 周 | 书面回复 🔴 HIGH 问题 + 附录 A 前 5 项 |
| Round 2 | T+2 周 | 管理层电话会议 — Q&A 追问 |
| Round 3 | T+3-4 周 | 现场 DD + Data Room 开放 |
| Round 4 | Term Sheet 前 | 最终条款确认 |
"""
