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

from services.helpers import docx_builder, search
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

CHAPTER_SYSTEM_PROMPT = """你是 BD Go 平台的专利情报分析师（代号：铁证），正在为 {query} 逐章撰写 IP 景观简报。

读者场景：BD 在评估一个公司/资产/靶点的专利保护状况，判断 FTO 风险和交易时间窗口。

硬规则：
1. **只写被要求的这一章**，直接输出 markdown，不要加前言或总结
2. **专利号必标** — 每条结论引用具体专利号（如有）
3. **到期日必写** — 专利到期日是 BD 最关注的时间线
4. **风险分级** — 用 🔴高 / 🟡中 / 🟢低 标注关键专利的 FTO 风险
5. **分管辖区** — 至少区分 US / EU / CN 三个法域
6. **中文为主**，专利号/专利类型保留英文
7. **不做法律意见** — 本报告不构成法律意见，正式 FTO 需委托律所
"""

# ── Chapter prompt templates ──────────────────────────────

_IP_CH1_PROMPT = """
## 任务：撰写第一章 执行摘要 & 风险概览（目标 ~600 字）

内容要求：
- 专利组合统计（总数/管辖区分布/类型分布）
- 3-5 条核心发现，每条附具体专利号
- 主要风险点概览（🔴🟡🟢 分级）
- 免责声明：本报告不构成法律意见

### 专利数据
{patents_block}

### 统计摘要
{stats_block}

### 前几章要点（上下文，不要重复）
{running_summary}

直接以 `## 第一章 执行摘要 & 风险概览` 开头输出 markdown：
"""

_IP_CH2_PROMPT = """
## 任务：撰写第二章 专利组合全貌（目标 ~1000 字）

内容要求：
- 按专利类型分类（Drug Product / Drug Substance / Method of Use / 其他）
- 按管辖区分布（US / EU / CN / JP / 其他）
- 按状态分布（有效 / 审查中 / 已过期）
- **必须包含统计表格**：

| 维度 | 详情 |
|---|---|
| 总专利数 | ... |
| 管辖区分布 | US: X / EU: X / CN: X / JP: X |
| 状态分布 | 有效: X / 审查中: X / 已过期: X |
| 专利类型 | Drug Product: X / Substance: X / Use: X |
| Orange Book 收录 | 是: X / 否: X |

- 主要权利人排名表（每个持有人专利数、代表专利号）

### 专利数据
{patents_block}

### 统计摘要
{stats_block}

### 前几章要点
{running_summary}

直接以 `## 第二章 专利组合全貌` 开头输出 markdown：
"""

_IP_CH3_PROMPT = """
## 任务：撰写第三章 专利到期日历（目标 ~800 字）

内容要求：
- 按到期日排序的关键专利列表（重点：未来 5 年）
- **必须包含表格**：

| 到期日 | 专利号 | 持有人 | 关联资产 | 专利类型 | PTE延期 | BD 含义 |
|---|---|---|---|---|---|---|

- LOE 窗口分析：专利悬崖在哪？仿制药/生物类似药可入场时间
- 段落：到期时间线对 BD 决策的含义

### 专利数据（按到期日排序）
{patents_block}

### 前几章要点
{running_summary}

直接以 `## 第三章 专利到期日历` 开头输出 markdown：
"""

_IP_CH4_PROMPT = """
## 任务：撰写第四章 核心阻断专利（目标 ~1200 字）

内容要求：
- 挑选 3-5 个最重要/最高风险的专利逐一分析
- 每个专利格式：
  - **专利号**: ...
  - **持有人**: ...
  - **到期日**: ...
  - **覆盖范围**: ...（权利要求摘要）
  - **FTO 风险**: 🔴高 / 🟡中 / 🟢低
  - **BD 含义**: ...
- **必须包含风险汇总表格**：

| 专利号 | 持有人 | 关联资产 | 到期日 | FTO风险 | 主要风险点 |
|---|---|---|---|---|---|

### 专利数据（含权利要求摘要）
{patents_block}

### 前几章要点
{running_summary}

直接以 `## 第四章 核心阻断专利` 开头输出 markdown：
"""

_IP_CH5_PROMPT = """
## 任务：撰写第五章 竞争对手专利格局（目标 ~1000 字）

内容要求：
- 在这个靶点/技术领域，各公司专利数量和布局策略
- **必须包含表格**：

| 持有人 | 专利数 | 代表专利号 | 关联资产 | 覆盖管辖区 | 技术分支 | 布局状态 |
|---|---|---|---|---|---|---|

- 分析：专利壁垒高度 + 谁掌握核心 IP + 竞争格局
- 空白区域提示：哪些技术方向专利相对稀疏

### 专利数据
{patents_block}

### 统计摘要（top holders）
{stats_block}

### 前几章要点
{running_summary}

直接以 `## 第五章 竞争对手专利格局` 开头输出 markdown：
"""

_IP_CH6_PROMPT = """
## 任务：撰写第六章 空白区域分析（目标 ~800 字）

内容要求：
- 哪些技术方向/靶点分支/适应症专利稀疏
- 进入机会：专利空白 = BD 进入机会
- 近期动态（基于 Web 检索）：专利诉讼/IPR/PTAB/和解/许可交易

{web_block}

### 前几章要点
{running_summary}

直接以 `## 第六章 空白区域分析` 开头输出 markdown：
"""

_IP_CH7_PROMPT = """
## 任务：撰写第七章 BD 战略建议（目标 ~600 字）

内容要求（基于前六章综合判断）：
- **In-licensing 机会**：哪些专利即将到期？到期前 License 策略
- **Out-licensing 价值**：该专利组合的许可价值评估
- **Generic/Biosimilar 窗口**：何时仿制药/生物类似药可入场
- **规避策略提示**：如果想绕开核心专利，需要关注哪些技术路径
- **Bottom Line**：3 句话 — IP 格局对 BD 的核心含义 + 推荐下一步行动

### 所有前章要点（本章决策依据）
{running_summary}

直接以 `## 第七章 BD 战略建议` 开头输出 markdown：
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
    estimated_seconds = 500
    category = "analysis"
    field_rules = {}

    # ── main ────────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = IPLandscapeInput(**params)
        query = inp.query.strip()
        if not query:
            raise ValueError("Query is required — provide a company, asset, or target name.")

        max_patents = max(10, min(inp.max_patents, 80))

        # Phase 1: Query CRM IP table
        ctx.log(f"Searching IP table for '{query}'...")
        patents = self._query_patents(ctx, query, inp.query_type, max_patents)
        ctx.log(f"Found {len(patents)} patents")

        if not patents and not inp.include_web_search:
            raise ValueError(
                f"No patents found for '{query}' in CRM. "
                "Try enabling web search or using a different query."
            )

        # Phase 2: Compute stats
        stats = self._compute_stats(patents)

        # Phase 2b: Web search
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Searching web for patent news...")
            web_results = self._run_web_searches(query)
            ctx.log(f"Web search returned {len(web_results)} results")
        else:
            ctx.log("Web search disabled")

        # Pre-format shared blocks
        patents_block = self._format_patents(patents)
        stats_block = self._format_stats(stats)
        web_block = format_web_results(web_results, inp.include_web_search)
        today = datetime.date.today().isoformat()

        system_prompt = CHAPTER_SYSTEM_PROMPT.format(query=query)

        # Phase 3: Generate chapters one by one
        chapter_texts: dict[int, str] = {}
        running_summary = ""

        # ── Chapter 1: 执行摘要 & 风险概览 ──
        ctx.log("第一章：执行摘要 & 风险概览...")
        ch1_prompt = _IP_CH1_PROMPT.format(
            patents_block=patents_block,
            stats_block=stats_block,
            running_summary=running_summary or "(无，这是第一章)",
        )
        chapter_texts[1] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch1_prompt}],
            max_tokens=1500,
        )
        running_summary += f"\n\n【第一章 执行摘要要点】{chapter_texts[1][:600]}"
        ctx.log(f"第一章完成（{len(chapter_texts[1])}字）")

        # ── Chapter 2: 专利组合全貌 ──
        ctx.log("第二章：专利组合全貌...")
        ch2_prompt = _IP_CH2_PROMPT.format(
            patents_block=patents_block,
            stats_block=stats_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[2] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch2_prompt}],
            max_tokens=2200,
        )
        running_summary += f"\n\n【第二章 专利组合要点】{chapter_texts[2][:600]}"
        ctx.log(f"第二章完成（{len(chapter_texts[2])}字）")

        # ── Chapter 3: 专利到期日历 ──
        ctx.log("第三章：专利到期日历...")
        ch3_prompt = _IP_CH3_PROMPT.format(
            patents_block=patents_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[3] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch3_prompt}],
            max_tokens=1800,
        )
        running_summary += f"\n\n【第三章 到期日历要点】{chapter_texts[3][:600]}"
        ctx.log(f"第三章完成（{len(chapter_texts[3])}字）")

        # ── Chapter 4: 核心阻断专利 ──
        ctx.log("第四章：核心阻断专利...")
        ch4_prompt = _IP_CH4_PROMPT.format(
            patents_block=patents_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[4] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch4_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第四章 核心阻断专利要点】{chapter_texts[4][:600]}"
        ctx.log(f"第四章完成（{len(chapter_texts[4])}字）")

        # ── Chapter 5: 竞争对手专利格局 ──
        ctx.log("第五章：竞争对手专利格局...")
        ch5_prompt = _IP_CH5_PROMPT.format(
            patents_block=patents_block,
            stats_block=stats_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[5] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch5_prompt}],
            max_tokens=2200,
        )
        running_summary += f"\n\n【第五章 竞争格局要点】{chapter_texts[5][:500]}"
        ctx.log(f"第五章完成（{len(chapter_texts[5])}字）")

        # ── Chapter 6: 空白区域分析 ──
        ctx.log("第六章：空白区域分析...")
        ch6_prompt = _IP_CH6_PROMPT.format(
            web_block=web_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[6] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch6_prompt}],
            max_tokens=1800,
        )
        running_summary += f"\n\n【第六章 空白区域要点】{chapter_texts[6][:500]}"
        ctx.log(f"第六章完成（{len(chapter_texts[6])}字）")

        # ── Chapter 7: BD 战略建议 ──
        ctx.log("第七章：BD 战略建议...")
        ch7_prompt = _IP_CH7_PROMPT.format(
            running_summary=running_summary[-1000:],
        )
        chapter_texts[7] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch7_prompt}],
            max_tokens=1500,
        )
        ctx.log(f"第七章完成（{len(chapter_texts[7])}字）")

        # Phase 4: Merge chapters + header
        header = (
            f"# {query} — IP Landscape Brief\n\n"
            f"> **生成日期**: {today} | **分析师**: BD Go (铁证) | "
            f"**数据源**: CRM ({len(patents)} 条专利) + Web\n"
            f"> ⚠️ 本报告不构成法律意见。正式 FTO 需委托专业知识产权律所。\n\n"
        )
        markdown = header + "\n\n".join(chapter_texts[i] for i in range(1, 8))

        total_chars = len(markdown)
        ctx.log(f"全部 7 章合并完成，总计约 {total_chars} 字")

        if total_chars < 500:
            raise RuntimeError("LLM returned empty or very short report")

        # Phase 4b: Save
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
                "chapters": 7,
                "total_chars": total_chars,
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
            conds.append('("关联资产" LIKE ? OR "权利要求摘要" LIKE ?)')
            params.extend([q, q])
        else:  # auto
            conds.append(
                '("关联公司" LIKE ? OR "关联资产" LIKE ? OR "专利持有人" LIKE ? '
                'OR "权利要求摘要" LIKE ?)'
            )
            params.extend([q, q, q, q])

        where = conds[0]
        sql = (
            'SELECT "专利号", "专利持有人", "关联资产", "关联公司", "专利类型", '
            '"申请日", "授权日", "到期日", "PTE延期到期日", "权利要求摘要", '
            '"专利族", "状态", "管辖区", "Orange_Book", "来源", "备注", "追踪状态" '
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

