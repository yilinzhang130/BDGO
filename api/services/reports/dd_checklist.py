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

from pydantic import BaseModel, Field

from services.helpers import docx_builder
from services.helpers.text import format_web_results, safe_slug, search_and_deduplicate
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)

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
    ("FIC", "Phase 1"):     ["high", "high", "medium", "medium", "medium", "medium", "low", "medium"],
    ("FIC", "Phase 2"):     ["medium", "high", "medium", "high", "medium", "medium", "medium", "medium"],
    ("FIC", "Phase 3"):     ["medium", "medium", "medium", "high", "high", "medium", "high", "high"],
    ("FIC", "Commercial"):  ["medium", "low", "medium", "medium", "medium", "high", "high", "high"],
    # BIC
    ("BIC", "Preclinical"): ["medium", "high", "medium", "low", "medium", "high", "low", "medium"],
    ("BIC", "Phase 1"):     ["medium", "medium", "medium", "high", "medium", "high", "medium", "medium"],
    ("BIC", "Phase 2"):     ["medium", "medium", "medium", "high", "medium", "high", "medium", "medium"],
    ("BIC", "Phase 3"):     ["medium", "low", "medium", "high", "high", "high", "high", "high"],
    ("BIC", "Commercial"):  ["medium", "low", "medium", "medium", "medium", "high", "high", "high"],
    # Me-too
    ("Me-too", "Preclinical"): ["medium", "low", "medium", "low", "medium", "high", "low", "medium"],
    ("Me-too", "Phase 1"):     ["medium", "low", "medium", "medium", "medium", "high", "medium", "medium"],
    ("Me-too", "Phase 2"):     ["medium", "low", "medium", "high", "high", "high", "high", "medium"],
    ("Me-too", "Phase 3"):     ["medium", "low", "medium", "high", "high", "high", "high", "medium"],
    ("Me-too", "Commercial"):  ["medium", "low", "medium", "medium", "medium", "high", "high", "high"],
    # Generic
    ("Generic", "Preclinical"): ["low", "low", "high", "low", "high", "high", "medium", "medium"],
    ("Generic", "Phase 1"):     ["low", "low", "high", "medium", "high", "high", "medium", "medium"],
    ("Generic", "Phase 2"):     ["low", "low", "high", "medium", "high", "high", "high", "medium"],
    ("Generic", "Phase 3"):     ["low", "low", "high", "medium", "high", "high", "high", "medium"],
    ("Generic", "Commercial"):  ["low", "low", "high", "low", "high", "high", "high", "medium"],
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
    asset_name: str | None = Field(None, description="Specific asset; blank = use CRM core pipeline")
    positioning_hint: Literal["FIC", "BIC", "Me-too", "Generic"] | None = None
    stage_hint: Literal["Preclinical", "Phase 1", "Phase 2", "Phase 3", "Commercial"] | None = None
    extra_context: str | None = Field(None, description="Anything the seller already disclosed or analyst already searched")
    include_web_search: bool = True


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 BD Go 平台的资深 Due Diligence 负责人，代表**买方（MNC / PE / Fund）**起草发给项目方 (biotech 卖方) 的尽调问题清单。

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


def _chapter_prompt(
    chapter_indices: list[int],   # 1-based
    chapter_titles: list[str],
    chapter_weights: list[str],
    asset_info: str,
    positioning: str,
    stage: str,
    extra_context: str,
    web_block: str,
) -> str:
    """Build a prompt for a batch of chapters."""
    chapter_lines = []
    for idx in chapter_indices:
        title = chapter_titles[idx - 1]
        weight = chapter_weights[idx - 1]
        n_questions = _QUESTIONS_PER_WEIGHT[weight]
        chapter_lines.append(
            f"### 章节 {title}  [权重: {_WEIGHT_EMOJI[weight]} · 建议 {n_questions} 个问题]"
        )

    weight_guidance = {
        "FIC":     "重点关注靶点验证 / MoA / translational biomarker；不要把 BIC 语言套进去",
        "BIC":     "**每章必须含 'vs 对标 FIC' 的 specific 对比问题**。没有 head-to-head 数据也要追问为什么没做",
        "Me-too":  "重点问 CMC / 市场 / 份额获取；科学章节简短带过",
        "Generic": "重点问 CMC 比对 / 杂质谱 / BE / 监管路径；临床章节聚焦 BE 而非 efficacy",
    }[positioning]

    return f"""## 任务：为以下章节各写一份 DD 问题清单

本次 DD 的基本情况：
- **定位**: {positioning} — {weight_guidance}
- **阶段**: {stage}

### 资产信息
{asset_info}

### 项目方已披露/分析师已搜到的上下文
{extra_context or '(无)'}

### Tavily 网络搜索结果（用于生成 specific 的问题，例如 "请说明你们如何回应 [竞品] 2025Q4 的 {{具体数据}}"）
{web_block}

### 要写的章节

{chr(10).join(chapter_lines)}

### 输出格式（严格遵守）

对每个章节，按以下模板输出 markdown：

```
## {{章节标题}}

**本章DD重点**: (1-2 句针对本资产 {positioning} + {stage} 组合的说明)

### 🔴 HIGH — 必答

- **{{问题编号}}**: {{问题}}
  - *期望答复*: {{数字/文件/表格/陈述}}

- **{{问题编号}}**: ...

### 🟡 MEDIUM — 重要

- **{{问题编号}}**: ...
  - *期望答复*: ...

### 🟢 LOW — 补充

- **{{问题编号}}**: ...
```

问题编号格式：`Q{{章号}}.{{序号}}`。例如 `Q2.1`, `Q2.2` ...。

**直接输出章节 markdown，不要前言或总结。**
"""


EXECUTIVE_SUMMARY_PROMPT = """## 任务：为本次 DD 写一份 Executive Summary

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


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────

class DDChecklistService(ReportService):
    slug = "dd-checklist"
    display_name = "DD 问题清单"
    description = (
        "针对单个 biotech 资产的**阶段-定位自适应** DD 尽调问卷。"
        "根据资产定位 (FIC/BIC/Me-too/Generic) × 阶段 (临床前→已上市) 自动裁剪 8 章节重点："
        "FIC 早期偏生物学+MoA+动物+CMC 基础；临床期偏试验设计+终点+早期毒；BIC 必问 vs 对标；仿制药重 CMC+BE+监管。"
        "输出 ~50-80 个中英双语问题，Word 格式可直接发项目方。"
    )
    chat_tool_name = "generate_dd_checklist"
    chat_tool_description = (
        "Generate a BD Due Diligence question checklist for a biotech asset. Stage × positioning adaptive: "
        "FIC-early focuses on biology/MoA/target validation/tox; BIC mandates vs-FIC head-to-head questions; "
        "Me-too/Generic emphasizes CMC/BE/market-entry. Queries CRM for company/asset facts + optional Tavily "
        "for competitor readouts and regulatory guidance. Returns 8-chapter Word doc (~60 questions, 120-180s)."
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
            inferred_note += "（⚠️ positioning 未能从 CRM 推断，默认 FIC；如不准请用 positioning_hint 重跑）"
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

        # Phase 5 — LLM: Executive Summary
        ctx.log("生成 Executive Summary...")
        exec_summary = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": EXECUTIVE_SUMMARY_PROMPT.format(
                    asset_info=asset_info,
                    positioning=positioning,
                    stage=stage,
                    extra_context_or_none=inp.extra_context or "(无)",
                ),
            }],
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
            )
            batch_md = ctx.llm(
                system=SYSTEM_PROMPT,
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

        # Phase 7 — Assemble markdown
        display_name = lead.get("资产名称") or (company_row or {}).get("客户名称") or inp.company
        header = (
            f"# {display_name} — BD Due Diligence 问题清单\n\n"
            f"> **生成日期**: {today}  |  **分析师**: BD Go (DD 尽调官)\n"
            f"> **定位**: {positioning}  |  **阶段**: {stage}  |  **CRM 命中**: "
            f"{'✓ ' + (company_row.get('客户名称', '?')) if company_row else '✗ 未命中（使用泛化模板）'}\n\n"
            f"> **使用说明**: 本清单按买方 DD 关注优先级排序。标 🔴 的问题为本资产 stage + positioning 下的核心风险，必须在首轮 DD 内获得答复；🟡 重要；🟢 补充。请项目方以「问题编号 + 书面答复 + 附件索引」格式回复。\n\n"
            "---\n\n"
        )

        body_chapters = []
        for idx in range(1, 9):
            if idx in chapter_texts:
                body_chapters.append(chapter_texts[idx].strip())
            else:
                body_chapters.append(
                    f"## {_CHAPTER_TITLES[idx-1]}\n\n"
                    f"[章节生成失败，请重跑任务或联系管理员]"
                )

        markdown = header + exec_summary.strip() + "\n\n---\n\n" + "\n\n---\n\n".join(body_chapters)
        markdown += "\n\n---\n\n" + self._appendix_section()

        if len(markdown) < 500:
            raise RuntimeError("DD checklist generation produced empty output")

        # Phase 8 — Save
        slug = safe_slug(display_name) or "asset"
        md_name = f"dd_checklist_{slug}_{today}.md"
        docx_name = f"dd_checklist_{slug}_{today}.docx"

        ctx.save_file(md_name, markdown, format="md")
        ctx.log("Markdown 已保存")

        ctx.log("渲染 Word 文档...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{display_name} DD 问题清单",
            subtitle=f"{positioning} · {stage} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(docx_name, docx_bytes, format="docx")
        ctx.log("Word 已保存")

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{display_name} DD Checklist",
                "company": inp.company,
                "asset": lead.get("资产名称") or inp.asset_name or "",
                "positioning": positioning,
                "stage": stage,
                "crm_hit_company": bool(company_row),
                "crm_hit_assets": len(assets),
                "web_results_count": len(web_results),
                "inferred_fallback": bool(inferred_note),
            },
        )

    # ── CRM queries ─────────────────────────────────────────
    def _query_company(self, ctx: ReportContext, company: str) -> dict | None:
        rows = ctx.crm_query(
            'SELECT "客户名称", "客户类型", "所处国家", "核心产品的阶段", '
            '"主要核心pipeline的名字", "BD跟进优先级" '
            'FROM "公司" WHERE "客户名称" ILIKE ? LIMIT 1',
            (f"%{company}%",),
        )
        return rows[0] if rows else None

    def _query_assets(
        self, ctx: ReportContext, company: str, asset_name: str | None
    ) -> list[dict]:
        if asset_name:
            rows = ctx.crm_query(
                'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
                '"疾病领域", "适应症", "差异化分级", "差异化描述", "Q总分", "技术平台类别" '
                'FROM "资产" WHERE "资产名称" ILIKE ? AND "所属客户" ILIKE ? LIMIT 10',
                (f"%{asset_name}%", f"%{company}%"),
            )
            if rows:
                return rows
        # Fallback: all assets of the company
        return ctx.crm_query(
            'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
            '"疾病领域", "适应症", "差异化分级", "差异化描述", "Q总分", "技术平台类别" '
            'FROM "资产" WHERE "所属客户" ILIKE ? LIMIT 10',
            (f"%{company}%",),
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

    def _split_chapters(
        self, batch_md: str, expected_indices: list[int]
    ) -> list[tuple[int, str]]:
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
