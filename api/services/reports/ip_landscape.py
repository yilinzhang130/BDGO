"""
IP Landscape — fourth report service.

Scoped-down port of ip-analyst skill. Original is a 13-chapter, 80-150 page
full FTO (Freedom to Operate) report with claim-by-claim analysis. Web version
produces a lightweight **IP Landscape Brief** (~3000 words, 6 chapters, .docx):

  1. Executive Summary (portfolio stats + key risks)
  2. Patent Portfolio Overview (by type, jurisdiction, status)
  3. Expiry Timeline (upcoming expirations + LOE windows)
  4. Key Blocking Patents (high-risk patents w/ claims summary)
  5. Competitor Patent Landscape (who else has patents in this space)
  6. BD Implications (in-licensing/out-licensing considerations)

Input: company name OR asset name OR target/technology keyword.
Data: CRM IP table (2749 patents) + optional Tavily web search.
"""

from __future__ import annotations

import datetime
import logging
import re
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


# ─────────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────────

class IPLandscapeInput(BaseModel):
    query: str  # company, asset, target, or technology keyword
    query_type: str = "auto"  # "company" | "asset" | "target" | "auto"
    include_web_search: bool = True
    max_patents: int = 40


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 BD Go 平台的专利情报分析师（代号：铁证）。你的任务：基于 CRM 专利数据 +
网络检索，撰写一份面向 BD 专业读者的 IP 景观简报。

读者场景：BD 在评估一个公司/资产/靶点的专利保护状况，判断 FTO 风险和交易时间窗口。

硬规则：
1. **专利号必标** — 每条结论都引用具体专利号
2. **到期日必写** — 专利的到期日是 BD 最关注的时间线
3. **风险分级** — 用 🔴高 / 🟡中 / 🟢低 标注每个关键专利的 FTO 风险
4. **分管辖区** — 至少区分 US / EU / CN 三个法域
5. **中文为主**，专利号/专利类型保留英文
6. **不做法律意见** — 明确标注"本报告不构成法律意见，正式 FTO 需委托律所"
7. **严格按 6 章输出**，不要加前言
"""

REPORT_PROMPT = """以下是 **{query}** 相关的 CRM 专利数据 + 网络检索结果。
请按 6 章结构撰写一份 ~3000 字的 IP 景观简报。

═════════════════════════════════════════════
## CRM 专利数据 ({n_patents} 条专利)
═════════════════════════════════════════════
{patents_block}

═════════════════════════════════════════════
## 专利统计摘要
═════════════════════════════════════════════
{stats_block}

═════════════════════════════════════════════
## 网络检索结果
═════════════════════════════════════════════
{web_block}

═════════════════════════════════════════════
## 输出格式
═════════════════════════════════════════════
直接输出 markdown（不加前言，不包代码块）：

```
# {query} — IP Landscape Brief

> **生成日期**: {today} | **分析师**: BD Go (铁证) | **数据源**: CRM ({n_patents} 条专利) + Web
> ⚠️ 本报告不构成法律意见。正式 FTO 需委托专业知识产权律所。

## Executive Summary

（3-5 条核心发现，每条带具体专利号）

## 1. Patent Portfolio Overview

（按专利类型分类 + 按管辖区分布 + 按状态统计）

| 维度 | 分布 |
|---|---|
| 总数 | ... |
| 管辖区 | US: X / EU: X / CN: X / JP: X |
| 状态 | 有效: X / 审查中: X / 已过期: X |
| 专利类型 | Drug Product: X / Drug Substance: X / Use: X |
| Orange Book | 是: X / 否: X |

## 2. Expiry Timeline

（按到期日排序的关键专利列表 + 到期窗口分析）

| 到期日 | 专利号 | 持有人 | 关联资产 | 专利类型 | PTE延期 | BD 含义 |
|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... |

（段落：最近 5 年的专利悬崖在哪？LOE 窗口对 generic/biosimilar 的影响）

## 3. Key Patents Analysis

（挑出 3-5 个最重要的专利，每个给出）:
- **专利号**: ...
- **持有人**: ...
- **到期日**: ...
- **覆盖范围**: ...（权利要求摘要，如有）
- **FTO 风险**: 🔴高 / 🟡中 / 🟢低
- **理由**: ...

## 4. Competitor Patent Landscape

（在这个靶点/技术领域，还有哪些公司持有专利？专利壁垒高度？）

| 持有人 | 专利数 | 代表专利号 | 关联资产 | 管辖区 | 状态 |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

## 5. Recent Developments

（基于 Web Search：近 12 个月的专利诉讼、IPR/PTAB 挑战、和解协议、专利许可交易）

## 6. BD Implications

- **In-licensing 机会**: 哪些专利即将到期？可以在到期前达成 License 降低竞争？
- **Out-licensing 价值**: 该专利组合的许可价值如何？
- **Generic/Biosimilar 窗口**: 什么时候仿制药/生物类似药可以进入？
- **规避策略提示**: 如果想避开核心专利，需要关注哪些技术路径？

## Bottom Line

3 句话：这个 IP 格局对 BD 的核心含义 + 推荐的下一步行动
```
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────

class IPLandscapeService(ReportService):
    slug = "ip-landscape"
    display_name = "IP Landscape"
    description = (
        "\u4e13\u5229\u666f\u89c2\u5206\u6790\u7b80\u62a5\u3002"
        "\u67e5\u8be2 CRM IP \u8868 (2749 \u6761\u4e13\u5229) + \u53ef\u9009 Tavily \u7f51\u641c\uff0c"
        "\u8f93\u51fa 6 \u7ae0\u8282 Word \u62a5\u544a\uff08\u7ec4\u5408\u6982\u89c8\u3001\u5230\u671f\u65f6\u95f4\u7ebf\u3001\u6838\u5fc3\u4e13\u5229\u3001\u7ade\u4e89\u683c\u5c40\u3001BD \u542f\u793a\uff09\u3002"
    )
    chat_tool_name = "analyze_ip"
    chat_tool_description = (
        "Generate an IP landscape brief for a company, asset, or target. "
        "Queries 2749 CRM patent records + optional web search for recent "
        "patent litigation and licensing news. Returns a 6-chapter Word report "
        "covering portfolio overview, expiry timeline, blocking patents, competitor "
        "landscape, and BD implications. ~120s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Company name, asset name, or target/technology keyword (e.g. 'Biogen', 'Tofersen', 'PD-L1 ADC').",
            },
            "query_type": {
                "type": "string",
                "enum": ["auto", "company", "asset", "target"],
                "description": "How to interpret the query. 'auto' tries all match types.",
                "default": "auto",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Search web for recent patent litigation/licensing news (default true).",
                "default": True,
            },
        },
        "required": ["query"],
    }
    input_model = IPLandscapeInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 120
    category = "analysis"
    field_rules = {}

    # ── main ────────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = IPLandscapeInput(**params)
        query = inp.query.strip()
        if not query:
            raise ValueError("Query is required — provide a company, asset, or target name.")

        max_patents = max(10, min(inp.max_patents, 80))

        # 1. Query CRM IP table
        ctx.log(f"Searching IP table for '{query}'...")
        patents = self._query_patents(ctx, query, inp.query_type, max_patents)
        ctx.log(f"Found {len(patents)} patents")

        if not patents and not inp.include_web_search:
            raise ValueError(
                f"No patents found for '{query}' in CRM. "
                "Try enabling web search or using a different query."
            )

        # 2. Compute stats
        stats = self._compute_stats(patents)

        # 3. Web search
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Searching web for patent news...")
            web_results = self._run_web_searches(query)
            ctx.log(f"Web search returned {len(web_results)} results")
        else:
            ctx.log("Web search disabled")

        # 4. LLM
        ctx.log("Generating IP landscape report via LLM...")
        prompt = REPORT_PROMPT.format(
            query=query,
            today=datetime.date.today().isoformat(),
            n_patents=len(patents),
            patents_block=self._format_patents(patents),
            stats_block=self._format_stats(stats),
            web_block=format_web_results(web_results, inp.include_web_search),
        )

        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=6000,
        )

        if not markdown or len(markdown.strip()) < 200:
            raise RuntimeError("LLM returned empty or very short report")

        # 5. Save
        slug = safe_slug(query)
        md_filename = f"ip_landscape_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(doc, title=query, subtitle="IP Landscape Brief")
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)

        docx_filename = f"ip_landscape_{slug}.docx"
        ctx.save_file(docx_filename, docx_bytes, format="docx")
        ctx.log("Word document saved")

        return ReportResult(
            markdown=markdown,
            meta={
                "query": query,
                "query_type": inp.query_type,
                "n_patents": len(patents),
                "web_results_count": len(web_results),
                "stats": stats,
                "chapters": 6,
            },
        )

    # ── CRM queries ─────────────────────────────────────────
    def _query_patents(
        self, ctx: ReportContext, query: str, query_type: str, limit: int,
    ) -> list[dict]:
        """Query IP table by company, asset, or keyword. Auto tries all."""
        conds: list[str] = []
        params: list[Any] = []
        q = f"%{query}%"

        if query_type == "company":
            conds.append('"关联公司" LIKE ?')
            params.append(q)
        elif query_type == "asset":
            conds.append('"关联资产" LIKE ?')
            params.append(q)
        elif query_type == "target":
            conds.append('("靶点" LIKE ? OR "关联资产" LIKE ? OR "权利要求摘要" LIKE ?)')
            params.extend([q, q, q])
        else:  # auto
            conds.append(
                '("关联公司" LIKE ? OR "关联资产" LIKE ? OR "专利持有人" LIKE ? '
                'OR "靶点" LIKE ? OR "权利要求摘要" LIKE ?)'
            )
            params.extend([q, q, q, q, q])

        where = conds[0]
        sql = (
            'SELECT "专利号", "专利持有人", "关联资产", "关联公司", "专利类型", '
            '"申请日", "授权日", "到期日", "PTE延期到期日", "权利要求摘要", '
            '"专利族", "状态", "管辖区", "Orange_Book", "来源", "备注", "靶点", '
            '"FTO风险等级", "核心权利要求", "绕开路径", "主要风险点" '
            f'FROM "IP" WHERE {where} '
            'ORDER BY "到期日" ASC '
            f'LIMIT {limit}'
        )
        return ctx.crm_query(sql, tuple(params))

    def _compute_stats(self, patents: list[dict]) -> dict:
        """Aggregate patent stats for the prompt."""
        if not patents:
            return {"total": 0}

        by_jurisdiction: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        orange_book = 0
        holders: dict[str, int] = {}

        for p in patents:
            j = p.get("管辖区") or "Unknown"
            by_jurisdiction[j] = by_jurisdiction.get(j, 0) + 1

            s = p.get("状态") or "Unknown"
            by_status[s] = by_status.get(s, 0) + 1

            t = p.get("专利类型") or "Other"
            # Simplify long type strings
            if len(t) > 30:
                t = t[:27] + "..."
            by_type[t] = by_type.get(t, 0) + 1

            if p.get("Orange_Book") in ("Yes", "yes", True, "true"):
                orange_book += 1

            h = p.get("专利持有人") or "Unknown"
            holders[h] = holders.get(h, 0) + 1

        return {
            "total": len(patents),
            "by_jurisdiction": dict(sorted(by_jurisdiction.items(), key=lambda x: -x[1])),
            "by_status": dict(sorted(by_status.items(), key=lambda x: -x[1])),
            "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])[:8]),
            "orange_book": orange_book,
            "top_holders": dict(sorted(holders.items(), key=lambda x: -x[1])[:10]),
        }

    # ── web search ──────────────────────────────────────────
    def _run_web_searches(self, query: str) -> list[dict]:
        queries = [
            f"{query} patent litigation PTAB IPR 2025 2026",
            f"{query} patent expiry generic biosimilar LOE 2025 2026",
        ]
        seen: set[str] = set()
        combined: list[dict] = []
        for q in queries:
            for r in search.search_web(q, max_results=3):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    combined.append({**r, "query": q})
        return combined

    # ── prompt formatting ──────────────────────────────────
    def _format_patents(self, patents: list[dict]) -> str:
        if not patents:
            return "(无匹配专利)"
        lines = []
        for p in patents:
            patent_no = p.get("专利号", "?")
            holder = p.get("专利持有人", "-")
            asset = p.get("关联资产", "-")
            company = p.get("关联公司", "-")
            ptype = p.get("专利类型", "-")
            expiry = p.get("到期日", "-")
            pte = p.get("PTE延期到期日", "")
            status = p.get("状态", "-")
            jur = p.get("管辖区", "-")
            ob = p.get("Orange_Book", "-")
            claims = (p.get("权利要求摘要") or "")[:200]
            target = p.get("靶点", "")
            risk = p.get("FTO风险等级", "")

            pte_note = f" (PTE→{pte})" if pte else ""
            risk_note = f" [FTO:{risk}]" if risk else ""
            target_note = f" 靶点:{target}" if target else ""

            lines.append(
                f"- **{patent_no}** ({jur}, {status}) | {holder} | "
                f"Asset: {asset} | Company: {company} | Type: {ptype} | "
                f"Expiry: {expiry}{pte_note} | OB: {ob}{risk_note}{target_note}"
            )
            if claims and claims != "None":
                lines.append(f"  Claims: {claims}")
        return "\n".join(lines)

    def _format_stats(self, stats: dict) -> str:
        if stats.get("total", 0) == 0:
            return "(无)"
        lines = [
            f"- Total: {stats['total']}",
            f"- By jurisdiction: {stats.get('by_jurisdiction', {})}",
            f"- By status: {stats.get('by_status', {})}",
            f"- By type (top 8): {stats.get('by_type', {})}",
            f"- Orange Book: {stats.get('orange_book', 0)}",
            f"- Top holders: {stats.get('top_holders', {})}",
        ]
        return "\n".join(lines)

