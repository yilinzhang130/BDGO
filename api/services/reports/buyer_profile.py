"""
MNC Buyer Profile — second worked example of a ReportService.

Pipeline:
  1. Fuzzy-lookup the company in MNC画像 (handles 'Pfizer' vs 'Pfizer (辉瑞)')
  2. Parse the pre-aggregated JSON intelligence (theses, sunk cost, capabilities)
  3. Optionally augment with Tavily web search (recent deals / exec signals)
  4. Single MiniMax call to produce a 6-chapter BD-style markdown report
  5. Save markdown + render styled .docx via docx_builder
  6. Return both files for download
"""

from __future__ import annotations

import datetime
import json
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
# Input schema
# ─────────────────────────────────────────────────────────────

class BuyerProfileInput(BaseModel):
    company_name: str
    focus_ta: str | None = None
    include_web_search: bool = True


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 BD Go 平台的投行买方分析师。你的任务：根据 CRM 预聚合的买方情报 +
最新网络检索结果，撰写一份面向 BD 专业读者的"买方需求画像简报"。

读者场景：BD 手里有资产要卖，想判断这家 MNC 会不会买、该怎么谈。

硬规则：
1. **数据说话** — 所有结论必须引用 CRM 数据或网络来源（标注 [CRM]、[Web]）
2. **简洁投行风格** — 像资深 MD 写内部简报，不写营销软文
3. **中文为主**，公司名/靶点/deal 类型保留英文
4. **回答"so what"** — 每条发现都连接到 BD 行动建议
5. **遇到数据缺失直接说** — 不要编造。标注 "[数据不足]" 比瞎写更专业
6. **严格按指定的 6 章结构输出**，不要增减章节，不要加前言
"""


REPORT_PROMPT = """以下是 MNC 买方 **{company}** 的 CRM 预聚合情报 + 网络检索结果，请
按指定的 6 章结构撰写一份 ~3500 字的 Word 简报。

═════════════════════════════════════════════
## CRM 情报 (来自 MNC画像 表)
═════════════════════════════════════════════
{crm_block}

═════════════════════════════════════════════
## 网络检索结果 (来自 Tavily)
═════════════════════════════════════════════
{web_block}

═════════════════════════════════════════════
## 输出格式
═════════════════════════════════════════════
严格按下面的 markdown 模板输出（不要加任何前言、不要用代码块包裹、直接输出 markdown）：

```
# {company} — Buyer Intelligence Brief

> **生成日期**: {today} | **分析师**: BD Go (探针) | **数据源**: CRM + Web Search

## Executive Summary

（3-5 条核心发现，每条 1-2 句，每条标注证据来源 [CRM] / [Web]）

- 发现 1...
- 发现 2...

## 1. Company DNA

（1 段散文，总结公司战略基因。引用 dna_summary、heritage_ta、deal_size_preference）

**Key Executives:**
- CEO: [姓名] — [背景 + BD 倾向]
- CSO: [姓名] — [背景]
- Head of BD: [姓名] — [背景]

## 2. Pipeline Gap Analysis {focus_instruction}

基于 commercial_capabilities + sunk_cost_by_ta 分析：

| Therapeutic Area | Current Strength | Identified Gap | So What |
|---|---|---|---|
| ... | ... | ... | ... |

（至少 3 行。每行给出具体的"so what" — 这个 gap 意味着 BD 机会在哪）

## 3. Historical BD Pattern

### 3.1 Deal Type Preference
（基于 deal_type_preference JSON，用一段话描述偏好许可/收购/合作的比例，数字带 %）

### 3.2 Signature Deals
（从 signature_deals 提取 2-3 笔代表交易，每笔给出 "what + why + size"）

### 3.3 BD Pattern Theses
（基于 bd_pattern_theses，每个 thesis 用 1 段话解读，带 invest_m 金额）

### 3.4 Sunk Cost by TA
| Therapeutic Area | Invested ($M) | Deal Count | Implication |
|---|---|---|---|
| ... | ... | ... | ... |

## 4. Recent Moves (Past 12 Months)

（基于 Web Search 结果，列出最近 12 个月的：新 BD 交易 / 管线新闻 / 高管变动。
每条注明 [Web - domain]。如果 Web Search 被关闭或无结果，写：
"> ⚠️ 本节未启用网络检索或未找到相关新闻。"）

## 5. BD Opportunity Matrix

（"如果你手里有什么资产，这家 MNC 会不会买？" — 给 5 种典型资产画像打分）

| Asset Profile | Fit Score | Why | What to Prepare |
|---|---|---|---|
| Phase 2/3 Oncology ADC | 高/中/低 | ... | ... |
| Early-stage Immunology | ... | ... | ... |
| ... | ... | ... | ... |

## 6. Bottom Line

（3-5 句话结论：这家 MNC 的买方特征总结 + 最佳接洽策略 + 需要规避的雷区）
```

**最后提醒**：直接开始写 markdown，不要说"好的我来写"这样的开场白，也不要用代码块包裹整个输出。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────

class BuyerProfileService(ReportService):
    slug = "buyer-profile"
    display_name = "MNC Buyer Profile"
    description = (
        "\u751f\u6210 MNC \u4e70\u65b9\u9700\u6c42\u753b\u50cf Word \u62a5\u544a\u3002"
        "\u8bfb\u53d6 CRM \u9884\u805a\u5408\u7684\u4e70\u65b9\u60c5\u62a5 + \u53ef\u9009 Tavily \u7f51\u7edc\u68c0\u7d22\u8865\u5145\u3002"
        "\u8f93\u51fa 6 \u7ae0\u7ed3\u6784\u3001~3500 \u5b57\u3001~8-12 \u9875 docx\u3002"
    )
    chat_tool_name = "generate_buyer_profile"
    chat_tool_description = (
        "Generate a BD-focused MNC buyer intelligence Word report. "
        "Input a company name (English or Chinese, fuzzy-matched) and receive a "
        "6-chapter brief covering Company DNA, Pipeline Gaps, BD Patterns, Recent Moves, "
        "and an Opportunity Matrix. Uses pre-aggregated CRM intelligence plus optional "
        "Tavily web search augmentation. Takes ~90-180s. Returns .docx + .md files."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "MNC company name, e.g. 'Pfizer' or 'Pfizer (\u8f89\u745e)'. Fuzzy-matched against MNC\u753b\u50cf table.",
            },
            "focus_ta": {
                "type": "string",
                "description": "Optional: restrict pipeline gap analysis to one therapeutic area, e.g. 'Oncology', 'Immunology'.",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Augment with Tavily web search for recent news (default true). Set false for faster CRM-only reports.",
                "default": True,
            },
        },
        "required": ["company_name"],
    }
    input_model = BuyerProfileInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 150
    category = "report"
    field_rules = {}  # no conditional visibility

    # ── main run ────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = BuyerProfileInput(**params)

        # 1. Fuzzy lookup the MNC画像 row
        ctx.log(f"Looking up {inp.company_name} in MNC画像...")
        profile = self._fuzzy_lookup(inp.company_name, ctx)
        if not profile:
            suggestions = self._suggest_companies(inp.company_name, ctx)
            msg = f"Company not found in MNC画像 table. Try one of: {', '.join(suggestions[:5])}"
            raise ValueError(msg)

        resolved_name = profile.get("company_name", inp.company_name)
        ctx.log(f"Resolved to: {resolved_name}")

        # 2. Parse JSON fields defensively
        parsed = self._parse_profile_json(profile)

        # 3. Optional web search augmentation
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Searching web for recent deals and news...")
            web_results = self._run_web_searches(resolved_name, parsed.get("heritage_ta", ""))
            ctx.log(f"Web search returned {len(web_results)} results")
        else:
            ctx.log("Web search disabled — CRM-only mode")

        # 4. Build LLM prompt + call
        ctx.log("Generating report via LLM...")
        crm_block = self._format_crm_block(profile, parsed)
        web_block = format_web_results(web_results, inp.include_web_search)
        focus_instruction = f"(\u91cd\u70b9\u5173\u6ce8 **{inp.focus_ta}**)" if inp.focus_ta else ""

        prompt = REPORT_PROMPT.format(
            company=resolved_name,
            crm_block=crm_block,
            web_block=web_block,
            today=datetime.date.today().isoformat(),
            focus_instruction=focus_instruction,
        )

        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=6000,
        )

        if not markdown or len(markdown.strip()) < 200:
            raise RuntimeError("LLM returned empty or very short report")

        # 5. Save markdown
        slug = safe_slug(resolved_name)
        md_filename = f"buyer_profile_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        # 6. Render to docx
        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{resolved_name}",
            subtitle="Buyer Intelligence Brief",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)

        docx_filename = f"buyer_profile_{slug}.docx"
        ctx.save_file(docx_filename, docx_bytes, format="docx")
        ctx.log("Word document saved")

        return ReportResult(
            markdown=markdown,
            meta={
                "company_name": resolved_name,
                "company_cn": profile.get("company_cn") or "",
                "heritage_ta": parsed.get("heritage_ta", ""),
                "focus_ta": inp.focus_ta,
                "include_web_search": inp.include_web_search,
                "web_results_count": len(web_results),
                "chapters": 6,
            },
        )

    # ── CRM lookup ──────────────────────────────────────────
    def _fuzzy_lookup(self, name: str, ctx: ReportContext) -> dict | None:
        """Try exact → LIKE 'name%' → LIKE '%name%'."""
        name = name.strip()
        if not name:
            return None

        row = ctx.crm_query_one(
            'SELECT * FROM "MNC\u753b\u50cf" WHERE "company_name" = ?',
            (name,),
        )
        if row:
            return row

        rows = ctx.crm_query(
            'SELECT * FROM "MNC\u753b\u50cf" WHERE "company_name" LIKE ? LIMIT 1',
            (f"{name}%",),
        )
        if rows:
            return rows[0]

        rows = ctx.crm_query(
            'SELECT * FROM "MNC\u753b\u50cf" WHERE "company_name" LIKE ? OR "company_cn" LIKE ? LIMIT 1',
            (f"%{name}%", f"%{name}%"),
        )
        return rows[0] if rows else None

    def _suggest_companies(self, name: str, ctx: ReportContext) -> list[str]:
        """Return up to 10 closest company names for error messages."""
        name = name.strip().lower()
        # Simple: return top 10 by LIKE match length ordering, fallback to first letter
        rows = ctx.crm_query(
            'SELECT "company_name" FROM "MNC\u753b\u50cf" WHERE lower("company_name") LIKE ? LIMIT 10',
            (f"%{name[:4]}%",),
        )
        suggestions = [r["company_name"] for r in rows if r.get("company_name")]
        if len(suggestions) < 5:
            # Pad with alphabetical neighbours
            extra = ctx.crm_query(
                'SELECT "company_name" FROM "MNC\u753b\u50cf" '
                'WHERE lower("company_name") >= ? ORDER BY "company_name" LIMIT 5',
                (name[:1],),
            )
            for r in extra:
                cn = r.get("company_name")
                if cn and cn not in suggestions:
                    suggestions.append(cn)
        return suggestions[:10]

    def _parse_profile_json(self, profile: dict) -> dict[str, Any]:
        """Parse JSON fields defensively, returning structured dict."""
        def _safe_json(raw: Any, default):
            if raw is None or raw == "":
                return default
            if isinstance(raw, (dict, list)):
                return raw
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("JSON parse failed for value: %r", str(raw)[:100])
                return default

        return {
            "heritage_ta": profile.get("heritage_ta") or "",
            "signature_deals": _safe_json(profile.get("signature_deals"), []),
            "commercial_capabilities": _safe_json(profile.get("commercial_capabilities"), {}),
            "regulatory_expertise": _safe_json(profile.get("regulatory_expertise"), {}),
            "bd_pattern_theses": _safe_json(profile.get("bd_pattern_theses"), []),
            "sunk_cost_by_ta": _safe_json(profile.get("sunk_cost_by_ta"), {}),
            "deal_type_preference": _safe_json(profile.get("deal_type_preference"), {}),
        }

    # ── web search ──────────────────────────────────────────
    def _run_web_searches(self, company: str, heritage_ta: str) -> list[dict]:
        """Run 3 Tavily queries, return deduplicated list of hits."""
        queries = [
            f"{company} BD deal licensing acquisition 2025 2026",
            f"{company} pipeline gap strategy" + (f" {heritage_ta}" if heritage_ta else ""),
            f"{company} CEO BD strategy 2026",
        ]
        seen_urls: set[str] = set()
        combined: list[dict] = []
        for q in queries:
            results = search.search_web(q, max_results=3)
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    combined.append({**r, "query": q})
        return combined

    # ── prompt formatting ──────────────────────────────────
    def _format_crm_block(self, profile: dict, parsed: dict) -> str:
        """Format MNC画像 row as a readable markdown block for the LLM prompt."""
        lines = []

        def _add(label: str, value: Any):
            if value is None or value == "" or value == {} or value == []:
                return
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            lines.append(f"**{label}**: {value}")

        _add("company_name", profile.get("company_name"))
        _add("company_cn", profile.get("company_cn"))
        _add("founded_year", profile.get("founded_year"))
        _add("heritage_ta", profile.get("heritage_ta"))
        _add("innovation_philosophy", profile.get("innovation_philosophy"))
        _add("risk_appetite", profile.get("risk_appetite"))
        _add("deal_size_preference", profile.get("deal_size_preference"))
        _add("annual_revenue", profile.get("annual_revenue"))
        _add("annual_revenue_year", profile.get("annual_revenue_year"))
        _add("ceo_name", profile.get("ceo_name"))
        _add("ceo_background", profile.get("ceo_background"))
        _add("cso_name", profile.get("cso_name"))
        _add("cso_background", profile.get("cso_background"))
        _add("head_bd_name", profile.get("head_bd_name"))
        _add("head_bd_background", profile.get("head_bd_background"))
        _add("dna_summary", profile.get("dna_summary"))
        _add("commercial_capabilities", parsed["commercial_capabilities"])
        _add("regulatory_expertise", parsed["regulatory_expertise"])
        _add("signature_deals", parsed["signature_deals"])
        _add("bd_pattern_theses", parsed["bd_pattern_theses"])
        _add("sunk_cost_by_ta", parsed["sunk_cost_by_ta"])
        _add("deal_type_preference", parsed["deal_type_preference"])

        if not lines:
            return "(\u65e0 CRM \u6570\u636e)"
        return "\n".join(lines)

    # ── helpers ─────────────────────────────────────────────
