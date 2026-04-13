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

CHAPTER_SYSTEM_PROMPT = """你是 BD Go 平台的投行买方分析师，正在为 {company} 逐章撰写买方需求画像简报。

读者场景：BD 手里有资产要卖，想判断这家 MNC 会不会买、该怎么谈。

硬规则：
1. **只写被要求的这一章**，直接输出 markdown，不要加前言或总结
2. **数据说话** — 结论引用 CRM 数据或网络来源，标注 [CRM] 或 [Web]
3. **简洁投行风格** — 像资深 MD 写内部简报，不写营销软文
4. **中文为主**，公司名/靶点/deal 类型保留英文
5. **回答"so what"** — 每条发现都连接到 BD 行动建议
6. **遇到数据缺失直接说** — 标注 "[数据不足]"，不要编造
"""

# ── Chapter prompt templates ──────────────────────────────

_BP_CH1_PROMPT = """
## 任务：撰写第一章 公司概况 & 战略定位（目标 ~800 字）

内容要求：
- 基本信息：成立年份、总部、市值/年收入、主要股东
- 战略重心：核心治疗领域、创新哲学（in-house vs BD驱动）
- 核心管线概览（已上市旗舰产品 + 核心在研）
- 引用 dna_summary、heritage_ta、innovation_philosophy、risk_appetite

{crm_block}

### 前几章要点（上下文，不要重复）
{running_summary}

直接以 `## 第一章 公司概况 & 战略定位` 开头输出 markdown：
"""

_BP_CH2_PROMPT = """
## 任务：撰写第二章 管线分析 & 专利悬崖（目标 ~1200 字）

内容要求：
- 核心产品/管线按治疗领域分层叙述
- 专利悬崖：未来 5 年 LOE 风险产品
- **必须包含表格**：

| 产品名 | 适应症 | 专利到期年 | 年销售额($B) | LOE风险评估 | 替代管线 |
|---|---|---|---|---|---|

- 分析：专利悬崖驱动的 BD 需求

{crm_block}

### 前几章要点
{running_summary}

直接以 `## 第二章 管线分析 & 专利悬崖` 开头输出 markdown：
"""

_BP_CH3_PROMPT = """
## 任务：撰写第三章 BD 历史 & 交易模式（目标 ~1200 字）

内容要求：
- 近 5 年重大交易（许可、收购、合作）；偏好阶段；付款结构
- **必须包含表格**：

| 交易年份 | 交易类型 | 对方 | 资产/靶点 | 阶段 | 首付款 | 总额 | 战略意图 |
|---|---|---|---|---|---|---|---|

- Deal type preference 分析（许可 vs 收购 vs 合作占比）
- BD Pattern Theses 解读（每个 thesis 附 invest_m 金额）
- Sunk Cost by TA 表格

{crm_block}

### 前几章要点
{running_summary}

直接以 `## 第三章 BD 历史 & 交易模式` 开头输出 markdown：
"""

_BP_CH4_PROMPT = """
## 任务：撰写第四章 管线空白 & 需求分析（目标 ~1200 字）

内容要求：
- 基于 commercial_capabilities + sunk_cost_by_ta 分析：哪些疾病领域缺货
- **必须包含表格**：

| 治疗领域 | 当前实力 | 已识别空白 | 优先需要什么 | So What |
|---|---|---|---|---|

- 至少覆盖 4-5 个治疗领域
- 分析：这家 MNC 最迫切的 BD 缺口在哪

{crm_block}

{focus_note}

### 前几章要点
{running_summary}

直接以 `## 第四章 管线空白 & 需求分析` 开头输出 markdown：
"""

_BP_CH5_PROMPT = """
## 任务：撰写第五章 中国 BD 机会矩阵（目标 ~1000 字）

内容要求：
- 中国资产与这家 MNC 需求的匹配分析
- **必须包含评分表格**（基于前四章的管线空白分析）：

| 资产类型/治疗领域 | 需求匹配度(1-5) | 战略契合度(1-5) | 竞争激烈度(1-5，越低越好) | 综合评分 | 推荐优先级 |
|---|---|---|---|---|---|

- Top 3 中国 BD 机会详细说明（每个给出：为什么这家 MNC 会买、怎么谈、什么时机）

{crm_block}

### 前几章要点
{running_summary}

直接以 `## 第五章 中国 BD 机会矩阵` 开头输出 markdown：
"""

_BP_CH6_PROMPT = """
## 任务：撰写第六章 高管画像 & 决策人（目标 ~800 字）

内容要求：
- CEO / CSO / Head of BD 背景、公开表态和 BD 倾向
- 格式：姓名 — 背景 — 公开表态（引述 + BD 含义）
- 决策流程：谁拍板、典型决策周期
- 基于 Web 近期新闻

{crm_block}

{web_block}

### 前几章要点
{running_summary}

直接以 `## 第六章 高管画像 & 决策人` 开头输出 markdown：
"""

_BP_CH7_PROMPT = """
## 任务：撰写第七章 交易结构参考（目标 ~800 字）

内容要求：
- 基于历史交易 comps：首付款范围 / 里程碑设置 / 版税区间
- 不同阶段资产（Phase 1/2/3）的典型交易结构
- 这家 MNC 特有的谈判偏好（从 deal_type_preference 和 signature_deals 推断）

{crm_block}

### 前几章要点
{running_summary}

直接以 `## 第七章 交易结构参考` 开头输出 markdown：
"""

_BP_CH8_PROMPT = """
## 任务：撰写第八章 BD 攻略 & 推荐行动（目标 ~600 字）

内容要求（基于前七章综合判断，给出可执行建议）：
- 最佳切入点（治疗领域 + 资产类型 + 阶段）
- 接触话术建议（突出哪些卖点、规避哪些雷区）
- 时机判断（什么时候接触最合适，结合催化剂和专利悬崖）
- 需要规避的雷区（这家 MNC 不会买什么）

### 所有前章要点（本章的决策依据）
{running_summary}

直接以 `## 第八章 BD 攻略 & 推荐行动` 开头输出 markdown：
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
    estimated_seconds = 600
    category = "report"
    field_rules = {}  # no conditional visibility

    # ── main run ────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = BuyerProfileInput(**params)

        # Phase 1: Fuzzy lookup the MNC画像 row
        ctx.log(f"Looking up {inp.company_name} in MNC画像...")
        profile = self._fuzzy_lookup(inp.company_name, ctx)
        if not profile:
            suggestions = self._suggest_companies(inp.company_name, ctx)
            msg = f"Company not found in MNC画像 table. Try one of: {', '.join(suggestions[:5])}"
            raise ValueError(msg)

        resolved_name = profile.get("company_name", inp.company_name)
        ctx.log(f"Resolved to: {resolved_name}")

        # Phase 2: Parse JSON fields defensively
        parsed = self._parse_profile_json(profile)

        # Phase 2b: Optional web search augmentation
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Searching web for recent deals and news...")
            web_results = self._run_web_searches(resolved_name, parsed.get("heritage_ta", ""))
            ctx.log(f"Web search returned {len(web_results)} results")
        else:
            ctx.log("Web search disabled — CRM-only mode")

        # Pre-format shared blocks
        crm_block = self._format_crm_block(profile, parsed)
        web_block = format_web_results(web_results, inp.include_web_search)
        today = datetime.date.today().isoformat()
        focus_note = f"> 重点关注治疗领域：**{inp.focus_ta}**" if inp.focus_ta else ""

        system_prompt = CHAPTER_SYSTEM_PROMPT.format(company=resolved_name)

        # Phase 3: Generate chapters one by one
        chapter_texts: dict[int, str] = {}
        running_summary = ""

        # ── Chapter 1: 公司概况 & 战略定位 ──
        ctx.log("第一章：公司概况 & 战略定位...")
        ch1_prompt = _BP_CH1_PROMPT.format(
            crm_block=crm_block,
            running_summary=running_summary or "(无，这是第一章)",
        )
        chapter_texts[1] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch1_prompt}],
            max_tokens=1800,
        )
        running_summary += f"\n\n【第一章 公司概况要点】{chapter_texts[1][:700]}"
        ctx.log(f"第一章完成（{len(chapter_texts[1])}字）")

        # ── Chapter 2: 管线分析 & 专利悬崖 ──
        ctx.log("第二章：管线分析 & 专利悬崖...")
        ch2_prompt = _BP_CH2_PROMPT.format(
            crm_block=crm_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[2] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch2_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第二章 管线/专利悬崖要点】{chapter_texts[2][:700]}"
        ctx.log(f"第二章完成（{len(chapter_texts[2])}字）")

        # ── Chapter 3: BD 历史 & 交易模式 ──
        ctx.log("第三章：BD 历史 & 交易模式...")
        ch3_prompt = _BP_CH3_PROMPT.format(
            crm_block=crm_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[3] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch3_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第三章 BD交易模式要点】{chapter_texts[3][:700]}"
        ctx.log(f"第三章完成（{len(chapter_texts[3])}字）")

        # ── Chapter 4: 管线空白 & 需求分析 ──
        ctx.log("第四章：管线空白 & 需求分析...")
        ch4_prompt = _BP_CH4_PROMPT.format(
            crm_block=crm_block,
            focus_note=focus_note,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[4] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch4_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第四章 管线空白要点】{chapter_texts[4][:700]}"
        ctx.log(f"第四章完成（{len(chapter_texts[4])}字）")

        # ── Chapter 5: 中国 BD 机会矩阵 ──
        ctx.log("第五章：中国 BD 机会矩阵...")
        ch5_prompt = _BP_CH5_PROMPT.format(
            crm_block=crm_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[5] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch5_prompt}],
            max_tokens=2200,
        )
        running_summary += f"\n\n【第五章 中国BD机会要点】{chapter_texts[5][:600]}"
        ctx.log(f"第五章完成（{len(chapter_texts[5])}字）")

        # ── Chapter 6: 高管画像 & 决策人 ──
        ctx.log("第六章：高管画像 & 决策人...")
        ch6_prompt = _BP_CH6_PROMPT.format(
            crm_block=crm_block,
            web_block=web_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[6] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch6_prompt}],
            max_tokens=1800,
        )
        running_summary += f"\n\n【第六章 高管画像要点】{chapter_texts[6][:500]}"
        ctx.log(f"第六章完成（{len(chapter_texts[6])}字）")

        # ── Chapter 7: 交易结构参考 ──
        ctx.log("第七章：交易结构参考...")
        ch7_prompt = _BP_CH7_PROMPT.format(
            crm_block=crm_block,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[7] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch7_prompt}],
            max_tokens=1800,
        )
        running_summary += f"\n\n【第七章 交易结构要点】{chapter_texts[7][:500]}"
        ctx.log(f"第七章完成（{len(chapter_texts[7])}字）")

        # ── Chapter 8: BD 攻略 & 推荐行动 ──
        ctx.log("第八章：BD 攻略 & 推荐行动...")
        ch8_prompt = _BP_CH8_PROMPT.format(
            running_summary=running_summary[-1000:],
        )
        chapter_texts[8] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch8_prompt}],
            max_tokens=1500,
        )
        ctx.log(f"第八章完成（{len(chapter_texts[8])}字）")

        # Phase 4: Merge chapters + header
        header = (
            f"# {resolved_name} — Buyer Intelligence Brief\n\n"
            f"> **生成日期**: {today} | **分析师**: BD Go (探针) | "
            f"**数据源**: CRM + Web Search\n\n"
        )
        markdown = header + "\n\n".join(chapter_texts[i] for i in range(1, 9))

        total_chars = len(markdown)
        ctx.log(f"全部 8 章合并完成，总计约 {total_chars} 字")

        if total_chars < 500:
            raise RuntimeError("LLM returned empty or very short report")

        # Phase 4b: Save markdown
        slug = safe_slug(resolved_name)
        md_filename = f"buyer_profile_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        # Phase 4c: Render to docx
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
                "chapters": 8,
                "total_chars": total_chars,
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
