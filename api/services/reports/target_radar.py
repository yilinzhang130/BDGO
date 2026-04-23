"""
Target Radar — fifth report service.

Scoped-down port of target-radar skill. Combines the two original modes
(landscape scan + deep target analysis) into a single comprehensive report.

Input: target name (e.g. "KRAS G12C", "PD-L1", "GLP-1R") or therapeutic area keyword.
Data: CRM assets (filtered by target/MOA) + CRM clinical trials + Tavily web search.
Output: 7-chapter Word report covering competition density, pipeline, clinical data,
        safety signals, MNC buyer fit, scientific momentum, and BD implications.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from crm_store import LIKE_ESCAPE, like_contains
from pydantic import BaseModel

from services.helpers import docx_builder, search
from services.helpers.text import format_web_results, safe_slug
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────────


class TargetRadarInput(BaseModel):
    target: str  # e.g. "KRAS G12C", "PD-L1", "GLP-1R", "NLRP3"
    indication: str | None = None  # optional narrowing: "NSCLC", "diabetes"
    include_web_search: bool = True
    max_crm_assets: int = 40


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 BD Go 平台的靶点战略分析师。你的任务：基于 CRM 资产+临床数据 + 网络检索，
撰写一份面向 BD 专业读者的靶点竞争雷达报告。

读者场景：BD 在评估一个靶点/机制是否值得追踪，需要回答三个核心问题：
1. 这个靶点现在多拥挤？（竞争密度）
2. 谁在做、做到什么阶段了？（管线格局）
3. 对 BD 意味着什么？（FIC/BIC机会 + 买方需求）

硬规则：
1. **竞争分级** — 用 🏖️蓝海(<3个管线) / 🌊适度(3-10) / 🔥激烈(10-20) / 💀红海(20+) 标注
2. **FIC/BIC判断** — 每个主要管线必须标注是 First-in-class / Best-in-class / Me-better / Me-too
3. **数据说话** — 引用具体公司名、资产名、临床阶段、Q-score（如有）
4. **中文为主**，靶点名/MOA/公司名保留英文
5. **严格 7 章输出**，不加前言
"""

REPORT_PROMPT = """以下是靶点 **{target}** 的 CRM 数据 + 网络检索结果。{indication_note}
请按 7 章结构撰写一份 ~3500 字的靶点竞争雷达报告。

═════════════════════════════════════════════
## CRM 资产数据 ({n_assets} 个管线资产)
═════════════════════════════════════════════
{assets_block}

═════════════════════════════════════════════
## CRM 临床试验数据 ({n_trials} 条)
═════════════════════════════════════════════
{trials_block}

═════════════════════════════════════════════
## 靶点统计摘要
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
# {target} — Target Competitive Radar

> **生成日期**: {today} | **分析师**: BD Go (靶点雷达) | **数据源**: CRM ({n_assets} 个管线, {n_trials} 条临床) + Web

## Executive Summary

（3-5 条核心发现，包含竞争等级判定 + FIC/BIC 机会判断）

## 1. Competition Density (竞争密度)

（全球该靶点管线总数 + 按阶段分布 + 竞争等级 🏖️/🌊/🔥/💀）

| 阶段 | 管线数 | 代表公司 |
|---|---|---|
| Approved | ... | ... |
| Phase 3 | ... | ... |
| Phase 2 | ... | ... |
| Phase 1 | ... | ... |
| Pre-clinical | ... | ... |

竞争等级判定：[🏖️蓝海 / 🌊适度 / 🔥激烈 / 💀红海]
（段落：竞争态势分析 + 进入壁垒判断）

## 2. Pipeline Landscape (管线格局)

（按阶段分层叙事，每个关键管线标注 FIC/BIC/Me-better/Me-too + 差异化描述）

| 资产名 | 公司 | MOA | 阶段 | 适应症 | 差异化 | FIC/BIC |
|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... |

## 3. Clinical Evidence (临床证据)

（已有的关键临床数据，按疗效排序）
- 最佳数据：[资产名] — ORR/PFS/OS（如有）
- 安全性信号：已知的 class effect toxicity（如有）
- Phase 3 成功/失败信号

## 4. Scientific Momentum (科学热度)

（基于 web search 结果评估）
- 2024-2026 文献/会议发表趋势
- 新发现（生物标志物、耐药机制、联合用药）
- 学术/工业共识成熟度

## 5. MNC Buyer Fit (买方需求匹配)

（基于 CRM 数据判断哪些 MNC 最可能对该靶点感兴趣）

| MNC | 匹配理由 | 需求强度 |
|---|---|---|
| ... | ... | ★★★★★ / ★★★★ / ★★★ |

## 6. BD Opportunity Assessment (BD 价值判断)

- **FIC 机会窗口**: 是否还有首家做的空间？需要什么差异化？
- **BIC 路径**: 已有玩家里谁最强？如何比它更好？
- **交易时机**: 现在是进入的好时机还是太晚/太早？
- **估值锚点**: 该靶点近 2 年有无代表性交易 comp？

## 7. Bottom Line & Recommendation

（3-5 句话总结：这个靶点值不值得追 + 推荐的 BD 行动方案）

评分卡:
| 维度 | 评分 (1-5) |
|---|---|
| 竞争空间 | /5 |
| 科学验证 | /5 |
| 安全性 | /5 |
| BD 价值 | /5 |
| **综合** | **/20** |
```
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class TargetRadarService(ReportService):
    slug = "target-radar"
    display_name = "Target Radar"
    description = (
        "\u9776\u70b9\u7ade\u4e89\u96f7\u8fbe\u5206\u6790\u3002"
        "\u8f93\u5165\u9776\u70b9/\u673a\u5236\u540d\u79f0\uff0c"
        "\u67e5\u8be2 CRM \u8d44\u4ea7+\u4e34\u5e8a\u6570\u636e + Web \u68c0\u7d22\uff0c"
        "\u8f93\u51fa 7 \u7ae0\u62a5\u544a\uff08\u7ade\u4e89\u5bc6\u5ea6\u3001\u7ba1\u7ebf\u683c\u5c40\u3001\u4e34\u5e8a\u8bc1\u636e\u3001"
        "\u79d1\u5b66\u70ed\u5ea6\u3001\u4e70\u65b9\u5339\u914d\u3001BD \u4ef7\u503c\u5224\u65ad\u3001\u8bc4\u5206\u5361\uff09\u3002"
    )
    chat_tool_name = "analyze_target"
    chat_tool_description = (
        "Generate a competitive radar report for a drug target or mechanism. "
        "Queries CRM assets and clinical trials filtered by target name, plus optional "
        "web search for scientific momentum and recent deals. Returns a 7-chapter Word "
        "report with competition density grading, FIC/BIC assessment, MNC buyer fit "
        "scoring, and a final scorecard (/20). ~120s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Target or mechanism name, e.g. 'KRAS G12C', 'PD-L1', 'GLP-1R', 'NLRP3', 'ADC'.",
            },
            "indication": {
                "type": "string",
                "description": "Optional indication to narrow (e.g. 'NSCLC', 'diabetes'). If omitted, covers all indications.",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Search web for scientific publications and deal news (default true).",
                "default": True,
            },
        },
        "required": ["target"],
    }
    input_model = TargetRadarInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 120
    category = "research"
    field_rules = {}

    # ── main ────────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = TargetRadarInput(**params)
        target = inp.target.strip()
        if not target:
            raise ValueError("Target is required — e.g. 'KRAS G12C', 'PD-L1'.")

        max_assets = max(10, min(inp.max_crm_assets, 60))
        indication_note = f"\n（聚焦适应症：**{inp.indication}**）" if inp.indication else ""

        # 1. CRM queries
        ctx.log(f"Querying CRM for target '{target}'...")
        assets = self._query_assets(ctx, target, inp.indication, max_assets)
        trials = self._query_clinical(ctx, target, inp.indication, limit=25)
        ctx.log(f"CRM: {len(assets)} assets, {len(trials)} trials")

        # 2. Stats
        stats = self._compute_stats(assets)

        # 3. Web search
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Searching web for target intelligence...")
            web_results = self._run_web_searches(target, inp.indication)
            ctx.log(f"Web: {len(web_results)} results")
        else:
            ctx.log("Web search disabled")

        # 4. LLM
        ctx.log("Generating target radar report...")
        prompt = REPORT_PROMPT.format(
            target=target,
            today=datetime.date.today().isoformat(),
            n_assets=len(assets),
            n_trials=len(trials),
            indication_note=indication_note,
            assets_block=self._format_assets(assets),
            trials_block=self._format_trials(trials),
            stats_block=self._format_stats(stats),
            web_block=format_web_results(web_results, inp.include_web_search),
        )

        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=7000,
        )

        if not markdown or len(markdown.strip()) < 200:
            raise RuntimeError("LLM returned empty report")

        # 5. Save
        slug = safe_slug(target)
        md_fn = f"target_radar_{slug}.md"
        ctx.save_file(md_fn, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(doc, title=target, subtitle="Target Competitive Radar")
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)

        docx_fn = f"target_radar_{slug}.docx"
        ctx.save_file(docx_fn, docx_bytes, format="docx")
        ctx.log("Word document saved")

        return ReportResult(
            markdown=markdown,
            meta={
                "target": target,
                "indication": inp.indication,
                "n_assets": len(assets),
                "n_trials": len(trials),
                "competition_level": stats.get("competition_level", "?"),
                "web_results": len(web_results),
                "chapters": 7,
            },
        )

    # ── CRM queries ─────────────────────────────────────────
    def _query_assets(
        self, ctx: ReportContext, target: str, indication: str | None, limit: int
    ) -> list[dict]:
        conds = [
            f'("靶点" LIKE ? {LIKE_ESCAPE} OR "作用机制(MOA)" LIKE ? {LIKE_ESCAPE} OR "资产名称" LIKE ? {LIKE_ESCAPE})'
        ]
        params: list[Any] = [like_contains(target)] * 3
        if indication:
            conds.append(f'"适应症" LIKE ? {LIKE_ESCAPE}')
            params.append(like_contains(indication))
        where = " AND ".join(conds)
        sql = (
            'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
            '"疾病领域", "适应症", "差异化分级", "差异化描述", "Q总分", '
            '"Q1_生物学", "Q2_药物形式", "Q3_临床监管", "Q4_商业交易性", '
            '"技术平台类别", "下一个临床节点", "节点预计时间", "竞品情况" '
            f'FROM "资产" WHERE {where} LIMIT {limit}'
        )
        return ctx.crm_query(sql, tuple(params))

    def _query_clinical(
        self, ctx: ReportContext, target: str, indication: str | None, limit: int
    ) -> list[dict]:
        conds = [f'("资产名称" LIKE ? {LIKE_ESCAPE} OR "适应症" LIKE ? {LIKE_ESCAPE})']
        params: list[Any] = [like_contains(target), like_contains(target)]
        if indication:
            conds.append(f'"适应症" LIKE ? {LIKE_ESCAPE}')
            params.append(like_contains(indication))
        where = " AND ".join(conds)
        sql = (
            'SELECT "试验ID", "资产名称", "公司名称", "适应症", "临床期次", '
            '"主要终点名称", "主要终点结果值", "主要终点_HR", "结果判定", '
            '"临床综合评分", "数据状态" '
            f'FROM "临床" WHERE {where} '
            'ORDER BY "临床综合评分" DESC LIMIT ?'
        )
        return ctx.crm_query(sql, tuple(params) + (limit,))

    def _compute_stats(self, assets: list[dict]) -> dict:
        n = len(assets)
        # Competition grading
        if n < 3:
            level = "🏖️ 蓝海 (Blue Ocean)"
        elif n <= 10:
            level = "🌊 适度竞争 (Moderate)"
        elif n <= 20:
            level = "🔥 激烈竞争 (Crowded)"
        else:
            level = "💀 红海 (Red Ocean)"

        by_phase: dict[str, int] = {}
        companies: set[str] = set()
        platforms: set[str] = set()
        for a in assets:
            phase = a.get("临床阶段") or "(unknown)"
            by_phase[phase] = by_phase.get(phase, 0) + 1
            c = a.get("所属客户")
            if c:
                companies.add(c)
            p = a.get("技术平台类别")
            if p:
                platforms.add(p)

        return {
            "total": n,
            "competition_level": level,
            "by_phase": dict(sorted(by_phase.items(), key=lambda x: -x[1])),
            "unique_companies": len(companies),
            "unique_platforms": len(platforms),
            "top_companies": list(companies)[:15],
        }

    # ── web search ──────────────────────────────────────────
    def _run_web_searches(self, target: str, indication: str | None) -> list[dict]:
        ind_suffix = f" {indication}" if indication else ""
        queries = [
            f"{target}{ind_suffix} clinical trial results 2025 2026",
            f"{target} pipeline competitive landscape FIC BIC 2025",
            f"{target}{ind_suffix} BD deal licensing 2025 2026",
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

    # ── formatting ──────────────────────────────────────────
    def _format_assets(self, assets: list[dict]) -> str:
        if not assets:
            return "(无匹配资产)"
        lines = []
        for a in assets:
            name = a.get("资产名称") or "(unnamed)"
            co = a.get("所属客户") or "-"
            tgt = a.get("靶点") or "-"
            moa = a.get("作用机制(MOA)") or "-"
            phase = a.get("临床阶段") or "-"
            ind = a.get("适应症") or "-"
            diff = a.get("差异化分级") or ""
            diff_desc = a.get("差异化描述") or ""
            q = a.get("Q总分") or ""
            comp = a.get("竞品情况") or ""
            extras = []
            if q:
                extras.append(f"Q={q}")
            if diff:
                extras.append(diff)
            if diff_desc:
                extras.append(diff_desc[:60])
            if comp:
                extras.append(f"竞品:{comp[:60]}")
            extra_str = " | ".join(extras) if extras else ""
            lines.append(
                f"- **{name}** ({co}) | {tgt} | {moa} | {phase} | {ind}"
                + (f" | {extra_str}" if extra_str else "")
            )
        return "\n".join(lines)

    def _format_trials(self, trials: list[dict]) -> str:
        if not trials:
            return "(无匹配临床)"
        lines = []
        for t in trials:
            tid = t.get("试验ID") or "?"
            asset = t.get("资产名称") or "?"
            co = t.get("公司名称") or "?"
            ind = t.get("适应症") or "-"
            phase = t.get("临床期次") or "-"
            ep = t.get("主要终点名称") or "-"
            val = t.get("主要终点结果值") or ""
            hr = t.get("主要终点_HR") or ""
            result = t.get("结果判定") or "-"
            score = t.get("临床综合评分") or ""
            data = f"{val}" + (f" HR={hr}" if hr else "")
            lines.append(
                f"- {tid}: {asset} ({co}) | {phase} | {ind} | "
                f"EP={ep} {data} | 判定={result} | Score={score}"
            )
        return "\n".join(lines)

    def _format_stats(self, stats: dict) -> str:
        if stats.get("total", 0) == 0:
            return "(无数据)"
        return (
            f"- Total pipelines: {stats['total']}\n"
            f"- Competition level: {stats['competition_level']}\n"
            f"- By phase: {stats['by_phase']}\n"
            f"- Unique companies: {stats['unique_companies']}\n"
            f"- Unique platforms: {stats['unique_platforms']}\n"
            f"- Top companies: {', '.join(stats['top_companies'][:10])}"
        )
