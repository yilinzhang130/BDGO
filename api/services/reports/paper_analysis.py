"""
Paper Analysis — worked example of a ReportService.

Port of the `paper-analyst` skill. Two modes:
  - single: deep-read a single paper (PMID/DOI/uploaded PDF)
  - survey: literature review on a research topic (PubMed search + cross-analysis)

Output: Markdown file saved to REPORTS_DIR/{task_id}/paper_{...}.md
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Literal

from config import BP_DIR
from pydantic import BaseModel

from services.external import pubmed
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input schema
# ─────────────────────────────────────────────────────────────


class PaperAnalysisInput(BaseModel):
    mode: Literal["single", "survey"] = "single"
    # single mode
    pmid: str | None = None
    doi: str | None = None
    filename: str | None = None  # Uploaded PDF under ~/.openclaw/workspace/BP/
    # survey mode
    topic: str | None = None
    max_papers: int = 15
    years_back: int = 3


# ─────────────────────────────────────────────────────────────
# LLM prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是生物医药 BD 团队的文献分析师（代号：探针）。

你的职责：读论文、提数据、对标竞品、给出 BD 判断。

核心原则：
1. **数据说话** — 不要写"显著改善"，要写"ORR 42% vs 18%, p<0.001"
2. **简洁直接** — 不要写学术评论，提数据、比竞品、下判断
3. **中文为主，术语保留英文** (如 ORR, mPFS, HR, ADC)
4. **每篇论文都要标注 DOI / PMID**
5. **BD 视角** — 这个数据支不支持交易？在竞争格局里处于什么位置？
"""

SINGLE_PAPER_PROMPT = """以下是一篇生物医药论文的元数据与摘要（可能还有部分正文）。

请按 **BD 文献分析师** 的视角，生成一份 Markdown 格式的结构化笔记。

# 论文信息
- **PMID**: {pmid}
- **DOI**: {doi}
- **标题**: {title}
- **期刊**: {journal}
- **年份**: {year}
- **作者**: {authors}

# 摘要 / 正文内容
{abstract}

---

**输出要求**：
1. 先判断论文类型（临床数据 / 技术平台 / 基础机制）
2. 按对应模板结构输出
3. 如果是临床数据论文，必须包含：
   - 试验概要（药物/靶点/适应症/设计/对照）
   - 疗效数据表（ORR/mPFS/mOS/HR/p-values，带数字）
   - 安全性（≥Grade 3 AE%、停药率、关键毒性）
   - **BD 判断**：数据支不支持交易？竞争位置如何？
4. 如果是技术/平台论文：一句话描述 → 技术原理 → 痛点→解决方案 → 验证数据 → 技术成熟度 → 谁在做 → BD 意义
5. 如果是基础机制：研究了什么 → 核心发现 → 验证程度 → 临床转化距离 → BD 判断

现在开始生成 Markdown 笔记（直接输出内容，不要加任何前言）："""

SURVEY_STRATEGY_PROMPT = """用户想做 "{topic}" 方向的文献综述。

请帮我拆解成一个 PubMed 检索策略，输出严格的 JSON 格式（不要其他内容）：

```json
{{
  "english_keywords": ["keyword1", "keyword2"],
  "pubmed_query": "PubMed 检索语法字符串",
  "sub_dimensions": ["子维度1", "子维度2", "子维度3"]
}}
```

要求：
- `english_keywords`: 3-5 个最关键的英文术语
- `pubmed_query`: 可直接粘贴到 PubMed 的检索语句，用 AND / OR 组合，例如 `"KRAS G12D" AND (cancer OR tumor)`
- `sub_dimensions`: 2-3 个研究子维度（如 "resistance mechanism" / "clinical efficacy" / "combination strategy"）

只输出 JSON，不要解释。"""

SURVEY_ANALYSIS_PROMPT = """你正在对 **"{topic}"** 方向做文献综述。已经从 PubMed 筛选出 {n} 篇文献，信息如下：

{papers_block}

---

请生成一份 **BD 视角的综述笔记**，结构严格按下面模板：

```markdown
# {topic} 文献综述

> **分析日期**: {today} | **纳入文献**: {n} 篇 | **分析师**: 探针

## Executive Summary / 核心判断
（3-5 句话，概括研究现状、关键结论、BD 意义）

## 一、研究现状概览
- 时间范围 / 文献类型分布（临床 vs 基础 vs 综述）
- 研究热度趋势（是否升温）

## 二、共识与发现
（2-4 条多篇文献支持的共识结论，每条标注引用的 PMID）

## 三、争议与未决问题
（论文之间的矛盾点 / 悬而未决的问题）

## 四、研究趋势
（方法学 / 研究范式的演变，新兴子方向）

## 五、BD 战略启示
- **机会信号**: 可以跟踪的方向/公司
- **风险信号**: 需要警惕的研究发现
- **行动建议**: 具体的 BD 跟进动作

## 六、纳入文献清单
| 作者 | 期刊 | 年份 | 核心结论 | DOI/PMID |
|------|------|------|----------|----------|
（列出所有 {n} 篇）

## 七、研究空白
（有 BD 价值但文献覆盖不足的方向）
```

**铁规则**：
- 所有数据都要带数字
- 每条结论都要标注是哪篇论文（用 PMID 或 [1][2] 引用）
- 中文为主，术语保留英文
- 不要写学术评论，要像资深 BD 同事的内部分析备忘录

现在直接输出 Markdown（不要加任何前言）："""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class PaperAnalysisService(ReportService):
    slug = "paper-analysis"
    display_name = "Paper Analysis"
    description = (
        "单篇论文精读或文献综述。单篇模式输入 PMID/DOI/上传 PDF，"
        "综述模式输入研究方向，自动 PubMed 搜索 10-20 篇高质量文献并交叉分析。"
    )
    chat_tool_name = "analyze_paper"
    chat_tool_description = (
        "Analyze a scientific paper or conduct a literature survey. "
        "Use mode='single' with pmid/doi/filename for single-paper deep-read. "
        "Use mode='survey' with topic for multi-paper literature review. "
        "Returns a Markdown BD-focused analysis with a download link."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["single", "survey"],
                "description": "single = deep-read one paper; survey = multi-paper literature review",
            },
            "pmid": {
                "type": "string",
                "description": "PubMed ID (single mode). E.g. '38912345'",
            },
            "doi": {
                "type": "string",
                "description": "DOI (single mode, alternative to pmid). E.g. '10.1038/s41586-024-xxxxx'",
            },
            "filename": {
                "type": "string",
                "description": "Filename of previously uploaded PDF under BP directory (single mode).",
            },
            "topic": {
                "type": "string",
                "description": "Research topic in Chinese or English (survey mode). E.g. 'KRAS G12D 耐药机制'",
            },
            "max_papers": {
                "type": "integer",
                "description": "Max papers in survey (default 15, range 5-25)",
                "default": 15,
            },
            "years_back": {
                "type": "integer",
                "description": "Restrict survey to last N years (default 3)",
                "default": 3,
            },
        },
        "required": ["mode"],
    }
    input_model = PaperAnalysisInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 60
    category = "research"
    field_rules = {
        "pmid": {"visible_when": {"mode": "single"}},
        "doi": {"visible_when": {"mode": "single"}},
        "filename": {"visible_when": {"mode": "single"}},
        "topic": {"visible_when": {"mode": "survey"}},
        "max_papers": {"visible_when": {"mode": "survey"}},
        "years_back": {"visible_when": {"mode": "survey"}},
    }

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = PaperAnalysisInput(**params)
        if inp.mode == "single":
            return self._run_single(inp, ctx)
        else:
            return self._run_survey(inp, ctx)

    # ── single paper mode ──────────────────────────────────
    def _run_single(self, inp: PaperAnalysisInput, ctx: ReportContext) -> ReportResult:
        # 1. Fetch paper content
        paper = self._fetch_paper(inp, ctx)
        if not paper:
            raise ValueError("Could not fetch paper. Provide a valid pmid, doi, or filename.")

        ctx.log(f"Loaded paper: {paper.get('title', '(untitled)')[:80]}")

        # 2. Build prompt
        prompt = SINGLE_PAPER_PROMPT.format(
            pmid=paper.get("pmid", "-"),
            doi=paper.get("doi", "-"),
            title=paper.get("title", "-"),
            journal=paper.get("journal", "-"),
            year=paper.get("year", "-"),
            authors=", ".join(paper.get("authors", [])[:5]) or "-",
            abstract=paper.get("abstract", "")[:15000],
        )

        # 3. LLM generate markdown
        ctx.log("Generating BD-focused analysis via LLM...")
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )

        if not markdown:
            raise RuntimeError("LLM returned empty response")

        # 4. Save to file
        slug = safe_slug(paper.get("title", "paper") or paper.get("pmid", "paper"))
        filename = f"paper_single_{slug}.md"
        ctx.save_file(filename, markdown, format="md")
        ctx.log("Done.")

        return ReportResult(
            markdown=markdown,
            meta={
                "mode": "single",
                "pmid": paper.get("pmid"),
                "doi": paper.get("doi"),
                "title": paper.get("title"),
                "journal": paper.get("journal"),
                "year": paper.get("year"),
            },
        )

    def _fetch_paper(self, inp: PaperAnalysisInput, ctx: ReportContext) -> dict:
        """Resolve paper content from pmid / doi / uploaded file."""
        if inp.pmid:
            ctx.log(f"Fetching PMID {inp.pmid} from PubMed...")
            return pubmed.fetch_single(pmid=inp.pmid)

        if inp.doi:
            ctx.log(f"Resolving DOI {inp.doi} via PubMed...")
            return pubmed.fetch_single(doi=inp.doi)

        if inp.filename:
            ctx.log(f"Extracting text from {inp.filename}...")
            filepath = BP_DIR / Path(inp.filename).name
            text = pubmed.extract_pdf_text(filepath)
            if not text:
                return {}
            # Try to pull title from first non-empty line
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            title = lines[0][:200] if lines else inp.filename
            return {
                "pmid": "-",
                "doi": "-",
                "title": title,
                "journal": "(uploaded PDF)",
                "year": "-",
                "authors": [],
                "abstract": text[:20000],
            }

        return {}

    # ── survey mode ────────────────────────────────────────
    def _run_survey(self, inp: PaperAnalysisInput, ctx: ReportContext) -> ReportResult:
        if not inp.topic:
            raise ValueError("Survey mode requires 'topic' parameter.")

        topic = inp.topic
        max_papers = max(5, min(inp.max_papers, 25))
        years_back = max(1, min(inp.years_back, 10))

        # 1. Build search strategy via LLM
        ctx.log(f"Planning search strategy for: {topic}")
        strategy_raw = ctx.llm(
            system="You are a biomedical literature search strategist. Output valid JSON only.",
            messages=[{"role": "user", "content": SURVEY_STRATEGY_PROMPT.format(topic=topic)}],
            max_tokens=512,
        )
        pubmed_query = self._extract_pubmed_query(strategy_raw, fallback=topic)
        ctx.log(f"Query: {pubmed_query}")

        # 2. Search PubMed
        ctx.log(f"Searching PubMed (last {years_back} years, max {max_papers} papers)...")
        pmids = pubmed.search_articles(
            query=pubmed_query,
            max_results=max_papers,
            sort="relevance",
            years_back=years_back,
        )

        if not pmids:
            raise RuntimeError(f"No papers found for topic '{topic}'. Try broader keywords.")

        ctx.log(f"Found {len(pmids)} PMIDs. Fetching metadata + abstracts...")

        # 3. Batch fetch metadata
        papers = pubmed.get_article_metadata(pmids)
        papers = [p for p in papers if p.get("title")]
        if not papers:
            raise RuntimeError("All papers returned empty metadata.")

        ctx.log(f"Loaded {len(papers)} papers. Generating cross-analysis...")

        # 4. Build the analysis prompt with all abstracts
        papers_block = self._format_papers_for_prompt(papers)
        analysis_prompt = SURVEY_ANALYSIS_PROMPT.format(
            topic=topic,
            n=len(papers),
            today=datetime.date.today().isoformat(),
            papers_block=papers_block,
        )

        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": analysis_prompt}],
            max_tokens=6000,
        )

        if not markdown:
            raise RuntimeError("LLM returned empty survey")

        # 5. Save file
        slug = safe_slug(topic)
        filename = f"paper_survey_{slug}.md"
        ctx.save_file(filename, markdown, format="md")
        ctx.log("Survey complete.")

        return ReportResult(
            markdown=markdown,
            meta={
                "mode": "survey",
                "topic": topic,
                "paper_count": len(papers),
                "query": pubmed_query,
                "years_back": years_back,
                "pmids": [p.get("pmid") for p in papers],
            },
        )

    # ── helpers ────────────────────────────────────────────
    def _extract_pubmed_query(self, raw: str, fallback: str) -> str:
        """Parse LLM strategy output, extract pubmed_query field with fallback."""
        import json

        # Try ```json ... ``` block
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        json_str = m.group(1) if m else raw

        try:
            data = json.loads(json_str)
            q = data.get("pubmed_query") or data.get("query")
            if isinstance(q, str) and q.strip():
                return q.strip()
        except Exception:
            pass

        # Fallback: convert Chinese topic to simple keyword query
        return fallback

    def _format_papers_for_prompt(self, papers: list[dict]) -> str:
        """Format paper list into a compact block for LLM context."""
        parts = []
        for i, p in enumerate(papers, 1):
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            block = (
                f"[{i}] PMID: {p.get('pmid', '-')} | DOI: {p.get('doi', '-')}\n"
                f"Title: {p.get('title', '-')}\n"
                f"Authors: {authors}\n"
                f"Journal: {p.get('journal', '-')} ({p.get('year', '-')})\n"
                f"Abstract:\n{p.get('abstract', '')[:2500]}\n"
            )
            parts.append(block)
        return "\n---\n".join(parts)
