"""
Clinical Guidelines Brief — sixth report service.

Input: disease name (Chinese or English).
Data: guidelines.db (79 guidelines, 611 recommendations, 379 biomarkers).
Output: Word .docx + markdown with treatment recommendations by line,
        biomarker testing panel, and BD implications.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import sqlite3
from typing import Any

from pydantic import BaseModel

from services.helpers import docx_builder
from services.helpers.text import format_web_results, safe_slug, search_and_deduplicate
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)

logger = logging.getLogger(__name__)

GUIDELINES_DB = os.path.expanduser("~/.openclaw/workspace/guidelines/guidelines.db")


def _gdb_query(sql: str, params: tuple = ()) -> list[dict]:
    """Query guidelines.db (read-only)."""
    if not os.path.exists(GUIDELINES_DB):
        return []
    conn = sqlite3.connect(f"file:{GUIDELINES_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────────

class ClinicalGuidelinesInput(BaseModel):
    disease: str
    source: str | None = None  # "NCCN" / "CSCO" / "ESMO" — omit for all
    include_web_search: bool = False  # guidelines are mostly from DB, web optional


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 BD Go 平台的临床指南分析师。你的任务：基于指南数据库中的结构化推荐数据，
撰写一份面向 BD 专业读者的临床指南简报。

读者场景：BD 在评估一个疾病的治疗格局，需要快速了解标准治疗方案、分子分型、生物标志物检测，
以及哪些治疗线上仍有 unmet need（= BD 机会）。

硬规则：
1. **数据全部来自指南数据库** — 不要编造推荐等级或证据级别
2. **推荐等级和证据级别必标** — I级/II级/III级 + 1A/1B/2A/2B
3. **中文为主**，药物名/靶点保留英文
4. **指南来源必标** — NCCN v3.2026 / CSCO 2026 / ESMO 2025 等
5. **严格按 5 章输出**
"""

REPORT_PROMPT = """以下是 **{disease}** 的临床指南数据库查询结果。
请按 5 章结构撰写一份 ~2500 字的临床指南简报。

═════════════════════════════════════════════
## 可用指南 ({n_guidelines} 部)
═════════════════════════════════════════════
{guidelines_block}

═════════════════════════════════════════════
## 治疗推荐 ({n_recs} 条)
═════════════════════════════════════════════
{recs_block}

═════════════════════════════════════════════
## 生物标志物 ({n_biomarkers} 条)
═════════════════════════════════════════════
{biomarkers_block}

═════════════════════════════════════════════
## 网络补充
═════════════════════════════════════════════
{web_block}

═════════════════════════════════════════════
## 输出格式
═════════════════════════════════════════════
直接输出 markdown（不加前言）：

```
# {disease} — Clinical Guidelines Brief

> **生成日期**: {today} | **分析师**: BD Go (指南) | **数据源**: Guidelines DB ({n_guidelines} 部指南, {n_recs} 条推荐, {n_biomarkers} 条标志物)

## Executive Summary

（3-5 条核心发现 — 标准治疗方案、关键分子分型、最大 unmet need）

## 1. 指南概览 (Guideline Sources)

（列出纳入的指南来源、版本、年份）

| 指南来源 | 版本 | 年份 | 覆盖范围 |
|---|---|---|---|
| ... | ... | ... | ... |

## 2. 治疗推荐 (Treatment Recommendations by Line)

### 一线治疗

| 推荐等级 | 证据级别 | 药物 | 药物类型 | 适应条件/人群 | 疗效概述 | 来源 |
|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... |

### 二线治疗

（同上格式）

### 三线及后线

（同上格式）

（段落：每个治疗线的 so what — BD 视角，哪些线上有 unmet need）

## 3. 生物标志物检测 (Biomarker Testing Panel)

| 标志物 | 检测方法 | 阳性阈值 | 临床意义 | 来源 |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

（段落：分子分型对 BD 选品的含义）

## 4. Unmet Needs & BD Opportunities

（基于前面的推荐和标志物，分析哪些治疗线/亚型仍缺有效方案）
- **Gap 1**: ...
- **Gap 2**: ...

## 5. Bottom Line

3 句话：这个疾病的治疗格局现状 + 最有 BD 价值的切入点
```
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────

class ClinicalGuidelinesService(ReportService):
    slug = "clinical-guidelines"
    display_name = "Clinical Guidelines"
    description = (
        "临床指南简报。查询指南数据库（79部指南/611条推荐/379条标志物），"
        "输出 5 章 Word 报告（指南概览、分治疗线推荐、生物标志物、未满足需求、BD 启示）。"
    )
    chat_tool_name = "generate_guidelines_report"
    chat_tool_description = (
        "Generate a clinical guidelines brief for a disease. Queries 79 guidelines, "
        "611 treatment recommendations, and 379 biomarkers from the structured guidelines "
        "database. Returns a 5-chapter Word report with treatment recs by line, biomarker "
        "panel, and BD opportunity analysis. Fast (~60s) since data is pre-structured."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "disease": {
                "type": "string",
                "description": "Disease name (Chinese or English), e.g. '非小细胞肺癌', 'NSCLC', 'breast cancer'.",
            },
            "source": {
                "type": "string",
                "description": "Optional guideline source filter: 'NCCN', 'CSCO', 'ESMO'. Omit for all.",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Augment with web search for latest guideline updates (default false — DB is usually sufficient).",
                "default": False,
            },
        },
        "required": ["disease"],
    }
    input_model = ClinicalGuidelinesInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 60
    category = "research"
    field_rules = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = ClinicalGuidelinesInput(**params)
        disease = inp.disease.strip()
        if not disease:
            raise ValueError("Disease name is required.")

        # 1. Query guidelines DB
        ctx.log(f"Querying guidelines DB for '{disease}'...")

        guidelines = _gdb_query(
            'SELECT * FROM "指南" WHERE "疾病" LIKE ?' + (
                ' AND "指南来源" LIKE ?' if inp.source else ''
            ),
            (f"%{disease}%",) + ((f"%{inp.source}%",) if inp.source else ()),
        )

        # Get guideline IDs for recommendation lookup
        guide_ids = [g["记录ID"] for g in guidelines]
        recs = []
        if guide_ids:
            placeholders = ",".join("?" * len(guide_ids))
            recs = _gdb_query(
                f'''SELECT r.*, g."疾病", g."指南来源", g."版本"
                    FROM "推荐" r JOIN "指南" g ON r."指南ID" = g."记录ID"
                    WHERE r."指南ID" IN ({placeholders})
                    ORDER BY r."治疗线", r."推荐等级"''',
                tuple(guide_ids),
            )

        biomarkers = _gdb_query(
            'SELECT * FROM "生物标志物" WHERE "疾病" LIKE ?',
            (f"%{disease}%",),
        )

        ctx.log(f"Found: {len(guidelines)} guidelines, {len(recs)} recommendations, {len(biomarkers)} biomarkers")

        if not guidelines and not recs and not biomarkers:
            raise ValueError(
                f"No guidelines data found for '{disease}'. "
                "Available diseases include: 非小细胞肺癌, 乳腺癌, 结直肠癌, 急性髓性白血病, 多发性骨髓瘤, etc."
            )

        # 2. Optional web search
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Searching web for latest guideline updates...")
            web_results = search_and_deduplicate([
                f"{disease} treatment guidelines update 2025 2026",
                f"{disease} NCCN CSCO ESMO new recommendation 2026",
            ], max_results_per_query=2)
            ctx.log(f"Web: {len(web_results)} results")

        # 3. LLM
        ctx.log("Generating guidelines report...")
        prompt = REPORT_PROMPT.format(
            disease=disease,
            today=datetime.date.today().isoformat(),
            n_guidelines=len(guidelines),
            n_recs=len(recs),
            n_biomarkers=len(biomarkers),
            guidelines_block=self._fmt_guidelines(guidelines),
            recs_block=self._fmt_recs(recs),
            biomarkers_block=self._fmt_biomarkers(biomarkers),
            web_block=format_web_results(web_results, inp.include_web_search),
        )

        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5000,
        )

        if not markdown or len(markdown.strip()) < 200:
            raise RuntimeError("LLM returned empty report")

        # 4. Save
        slug = safe_slug(disease)
        ctx.save_file(f"guidelines_{slug}.md", markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(doc, title=disease, subtitle="Clinical Guidelines Brief")
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"guidelines_{slug}.docx", docx_bytes, format="docx")
        ctx.log("Done.")

        return ReportResult(
            markdown=markdown,
            meta={
                "disease": disease,
                "source": inp.source,
                "n_guidelines": len(guidelines),
                "n_recs": len(recs),
                "n_biomarkers": len(biomarkers),
                "chapters": 5,
            },
        )

    # ── formatting ──────────────────────────────────────────
    def _fmt_guidelines(self, rows: list[dict]) -> str:
        if not rows:
            return "(无)"
        return "\n".join(
            f"- {g.get('指南来源','?')} {g.get('版本','?')} ({g.get('发布年份','?')}) — {g.get('疾病','?')}"
            + (f" [{g.get('疾病亚型','')}]" if g.get("疾病亚型") else "")
            for g in rows
        )

    def _fmt_recs(self, rows: list[dict]) -> str:
        if not rows:
            return "(无)"
        lines = []
        for r in rows:
            drug = r.get("药物") or "-"
            dtype = r.get("药物类型") or ""
            line_n = r.get("治疗线") or "-"
            grade = r.get("推荐等级") or "-"
            evidence = r.get("证据级别") or "-"
            condition = r.get("适应条件") or ""
            population = r.get("适应人群") or ""
            efficacy = r.get("疗效概述") or ""
            ae = r.get("不良反应") or ""
            source = r.get("指南来源") or ""
            version = r.get("版本") or ""
            lines.append(
                f"- [{line_n}] {grade}/{evidence} **{drug}** ({dtype}) | "
                f"条件:{condition} | 人群:{population} | "
                f"疗效:{efficacy} | AE:{ae} | 来源:{source} {version}"
            )
        return "\n".join(lines)

    def _fmt_biomarkers(self, rows: list[dict]) -> str:
        if not rows:
            return "(无)"
        return "\n".join(
            f"- **{b.get('标志物','?')}** | 方法:{b.get('检测方法','-')} | "
            f"阈值:{b.get('阳性阈值','-')} | 意义:{b.get('临床意义','-')} | "
            f"来源:{b.get('指南来源','-')}"
            for b in rows
        )
