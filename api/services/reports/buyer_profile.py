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

import concurrent.futures
import datetime
import json
import logging
import os
import sys
from typing import Any

# crm_db lives in the workspace scripts directory, not on the default Python
# path. Import it once at module load so callers don't race on sys.path.insert.
_scripts_dir = os.path.expanduser("~/.openclaw/workspace/scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
try:
    import crm_db as _crm_db
except ImportError:
    _crm_db = None  # type: ignore[assignment]

from pydantic import BaseModel

from services.document import docx_builder
from services.quality import audit_to_dict, validate_markdown
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import (
    format_web_results,
    safe_json_loads,
    safe_slug,
    search_and_deduplicate,
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
2. **数据说话** — 结论引用 BDGO数据库 或网络来源，标注 [BDGO] 或 [Web]
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

        # Phase 1: Resolve company via shared fuzzy resolver
        ctx.log(f"Looking up {inp.company_name} in MNC画像...")
        from services.crm.resolve import resolve_mnc

        resolve = resolve_mnc(inp.company_name)
        profile = resolve.row
        web_only = profile is None

        if web_only:
            ctx.log(f"'{inp.company_name}' not in CRM — switching to web-enriched mode")
            if resolve.suggestions:
                ctx.log(f"Closest matches in MNC画像: {', '.join(resolve.suggestions[:3])}")
            resolved_name = inp.company_name
        else:
            resolved_name = resolve.canonical or profile.get("company_name", inp.company_name)
            if resolve.fuzzy:
                ctx.log(f"Fuzzy-matched '{inp.company_name}' → '{resolved_name}'")
            else:
                ctx.log(f"Resolved to: {resolved_name}")

        # Phase 2: Parse JSON fields defensively
        parsed = self._parse_profile_json(profile or {})

        # Phase 2b: Web search (mandatory in web-only mode)
        web_results: list[dict] = []
        if inp.include_web_search or web_only:
            ctx.log("Searching web for deals, strategy, and company profile...")
            if web_only:
                web_results = self._run_expanded_web_searches(resolved_name)
            else:
                web_results = self._run_web_searches(resolved_name, parsed.get("heritage_ta", ""))
            ctx.log(f"Web search returned {len(web_results)} results")
        else:
            ctx.log("Web search disabled — CRM-only mode")

        # Pre-format shared blocks
        if web_only:
            crm_block = self._build_web_crm_block(resolved_name, web_results)
        else:
            crm_block = self._format_crm_block(profile, parsed)
        web_block = format_web_results(web_results, inp.include_web_search or web_only)
        today = datetime.date.today().isoformat()
        focus_note = f"> 重点关注治疗领域：**{inp.focus_ta}**" if inp.focus_ta else ""

        system_prompt = CHAPTER_SYSTEM_PROMPT.format(company=resolved_name)

        # Phase 3: Generate chapters in parallel batches.
        #
        # Dependency analysis: each chapter uses running_summary[-1000:], which
        # covers roughly the last 1-2 chapter summaries. The strict chain is
        # Ch1 → Ch2 → ... → Ch8, but we can tolerate each batch sharing a
        # snapshot of the summary rather than seeing every predecessor's output.
        # This reduces wall-clock time from ~120s to ~40s at the cost of each
        # batch member not seeing its co-batch siblings' summaries.
        #
        # Batch layout:
        #   Seq  : Ch1  (bootstraps context — no predecessor)
        #   Par A: Ch2, Ch3  (parallel, both see Ch1 snapshot)
        #   Par B: Ch4, Ch5, Ch6, Ch7  (parallel, all see Ch1+2+3 snapshot)
        #   Seq  : Ch8  (final synthesis — needs full accumulated context)

        chapter_texts: dict[int, str] = {}
        running_summary = ""

        def _run_ch(ch_num: int, prompt: str, max_tok: int) -> tuple[int, str]:
            result = ctx.llm(
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tok,
                label=f"bp_ch{ch_num}",
            )
            ctx.log(f"第{ch_num}章完成（{len(result)}字）")
            return ch_num, result

        # ── Batch 0: Chapter 1 (sequential — bootstraps context) ──
        ctx.log("第一章：公司概况 & 战略定位...")
        _, chapter_texts[1] = _run_ch(
            1,
            _BP_CH1_PROMPT.format(
                crm_block=crm_block,
                running_summary="(无，这是第一章)",
            ),
            1800,
        )
        running_summary += f"\n\n【第一章 公司概况要点】{chapter_texts[1][:700]}"

        # ── Batch A: Chapters 2 & 3 in parallel ──
        ctx.log("第二、三章并行处理中...")
        snap_a = running_summary[-1000:]
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="bp_ch"
        ) as pool:
            futs_a = {
                pool.submit(
                    _run_ch,
                    2,
                    _BP_CH2_PROMPT.format(crm_block=crm_block, running_summary=snap_a),
                    2500,
                ),
                pool.submit(
                    _run_ch,
                    3,
                    _BP_CH3_PROMPT.format(crm_block=crm_block, running_summary=snap_a),
                    2500,
                ),
            }
            for fut in concurrent.futures.as_completed(futs_a):
                ch_num, text = fut.result()
                chapter_texts[ch_num] = text
        running_summary += f"\n\n【第二章 管线/专利悬崖要点】{chapter_texts[2][:700]}"
        running_summary += f"\n\n【第三章 BD交易模式要点】{chapter_texts[3][:700]}"

        # ── Batch B: Chapters 4-7 in parallel ──
        ctx.log("第四-七章并行处理中...")
        snap_b = running_summary[-1000:]
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="bp_ch"
        ) as pool:
            futs_b = {
                pool.submit(
                    _run_ch,
                    4,
                    _BP_CH4_PROMPT.format(
                        crm_block=crm_block,
                        focus_note=focus_note,
                        running_summary=snap_b,
                    ),
                    2500,
                ),
                pool.submit(
                    _run_ch,
                    5,
                    _BP_CH5_PROMPT.format(crm_block=crm_block, running_summary=snap_b),
                    2200,
                ),
                pool.submit(
                    _run_ch,
                    6,
                    _BP_CH6_PROMPT.format(
                        crm_block=crm_block,
                        web_block=web_block,
                        running_summary=snap_b,
                    ),
                    1800,
                ),
                pool.submit(
                    _run_ch,
                    7,
                    _BP_CH7_PROMPT.format(crm_block=crm_block, running_summary=snap_b),
                    1800,
                ),
            }
            for fut in concurrent.futures.as_completed(futs_b):
                ch_num, text = fut.result()
                chapter_texts[ch_num] = text
        running_summary += f"\n\n【第四章 管线空白要点】{chapter_texts[4][:700]}"
        running_summary += f"\n\n【第五章 中国BD机会要点】{chapter_texts[5][:600]}"
        running_summary += f"\n\n【第六章 高管画像要点】{chapter_texts[6][:500]}"
        running_summary += f"\n\n【第七章 交易结构要点】{chapter_texts[7][:500]}"

        # ── Batch C: Chapter 8 (sequential — final synthesis) ──
        ctx.log("第八章：BD 攻略 & 推荐行动...")
        _, chapter_texts[8] = _run_ch(
            8,
            _BP_CH8_PROMPT.format(running_summary=running_summary[-1000:]),
            1500,
        )

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

        # Phase 5: CRM write-back for web-enriched companies
        if web_only:
            ctx.log("Extracting structured data for CRM enrichment...")
            self._enrich_and_save_to_crm(resolved_name, markdown, ctx)

        # Phase 6: Schema validation (non-blocking — failures still ship the report)
        schema_audit: dict = {}
        try:
            audit = validate_markdown(markdown, mode="mnc")
            schema_audit = audit_to_dict(audit)
            ctx.log(
                f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}"
            )
        except Exception:
            logger.exception("Schema validation failed for task %s", ctx.task_id)
            schema_audit = {"error": "validator_exception"}

        return ReportResult(
            markdown=markdown,
            meta={
                "company_name": resolved_name,
                "company_cn": (profile or {}).get("company_cn") or "",
                "heritage_ta": parsed.get("heritage_ta", ""),
                "focus_ta": inp.focus_ta,
                "include_web_search": inp.include_web_search,
                "web_only": web_only,
                "web_results_count": len(web_results),
                "chapters": 8,
                "total_chars": total_chars,
                "schema_audit": schema_audit,
            },
        )

    def _parse_profile_json(self, profile: dict) -> dict[str, Any]:
        """Parse JSON fields defensively, returning structured dict."""
        return {
            "heritage_ta": profile.get("heritage_ta") or "",
            "signature_deals": safe_json_loads(profile.get("signature_deals"), []),
            "commercial_capabilities": safe_json_loads(profile.get("commercial_capabilities"), {}),
            "regulatory_expertise": safe_json_loads(profile.get("regulatory_expertise"), {}),
            "bd_pattern_theses": safe_json_loads(profile.get("bd_pattern_theses"), []),
            "sunk_cost_by_ta": safe_json_loads(profile.get("sunk_cost_by_ta"), {}),
            "deal_type_preference": safe_json_loads(profile.get("deal_type_preference"), {}),
        }

    # ── web search ──────────────────────────────────────────
    def _run_web_searches(self, company: str, heritage_ta: str) -> list[dict]:
        """Run 3 Tavily queries to augment an existing CRM profile."""
        queries = [
            f"{company} BD deal licensing acquisition 2025 2026",
            f"{company} pipeline gap strategy" + (f" {heritage_ta}" if heritage_ta else ""),
            f"{company} CEO BD strategy 2026",
        ]
        return search_and_deduplicate(queries, max_results_per_query=3)

    def _run_expanded_web_searches(self, company: str) -> list[dict]:
        """Run 6 Tavily queries when no CRM data is available at all."""
        queries = [
            f"{company} pharmaceutical company overview revenue history",
            f"{company} therapeutic areas pipeline approved drugs 2025",
            f"{company} BD deal licensing acquisition M&A 2024 2025",
            f"{company} CEO CSO head of business development background",
            f"{company} strategic priorities pipeline gaps needs",
            f"{company} China partnerships collaboration licensing",
        ]
        return search_and_deduplicate(queries, max_results_per_query=4)

    def _build_web_crm_block(self, company: str, web_results: list[dict]) -> str:
        """Build a pseudo-CRM block from web search results when company isn't in CRM."""
        if not web_results:
            return f"**[数据来源：网络搜索]** (无结果)\n\n注意：{company} 在 CRM 中无数据，请通过网络数据分析。"
        lines = [f"**company_name**: {company}", "**[数据来源：网络搜索 — 非 CRM 数据]**\n"]
        for r in web_results[:8]:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            url = r.get("url", "")
            if snippet:
                lines.append(f"**{title}** ({url})\n{snippet}\n")
        return "\n".join(lines)

    def _enrich_and_save_to_crm(self, company_name: str, markdown: str, ctx: ReportContext) -> None:
        """Extract structured fields from the report and upsert to MNC画像."""
        extract_prompt = (
            f"从以下MNC买方报告中提取结构化数据，仅包含报告中有明确依据的字段，不要编造。\n"
            f"以JSON格式输出以下字段（缺失则省略）：\n"
            f"company_name, company_cn, heritage_ta, innovation_philosophy, dna_summary, "
            f"annual_revenue, annual_revenue_year, ceo_name, head_bd_name, risk_appetite, "
            f"deal_size_preference, deal_type_preference（JSON对象）, sunk_cost_by_ta（JSON对象）\n\n"
            f"报告内容（前3000字）：\n{markdown[:3000]}"
        )
        try:
            raw = ctx.llm(
                system="数据提取助手：从报告中提取结构化字段，以JSON输出，不要用markdown代码块。",
                messages=[{"role": "user", "content": extract_prompt}],
                max_tokens=800,
            )
            from services.external.llm import _extract_json_object

            data = _extract_json_object(raw) or {}
            if not data.get("company_name"):
                data["company_name"] = company_name
            data["last_updated"] = datetime.date.today().isoformat()

            # JSON-encode any dict/list values to match column storage format
            for key in (
                "deal_type_preference",
                "sunk_cost_by_ta",
                "signature_deals",
                "bd_pattern_theses",
                "commercial_capabilities",
                "regulatory_expertise",
            ):
                if key in data and isinstance(data[key], (dict, list)):
                    data[key] = json.dumps(data[key], ensure_ascii=False)

            # Write to CRM via crm_db (works on VM/PG; no-op on local SQLite read-only)
            if _crm_db is None:
                ctx.log("CRM enrichment skipped — crm_db not importable")
                return
            if not _crm_db._is_pg():
                ctx.log(
                    "CRM enrichment skipped — SQLite snapshot is read-only (run on VM to persist)"
                )
                return
            action, key = _crm_db.upsert_row("MNC画像", data)
            ctx.log(f"CRM enrichment: {action} MNC画像 entry for '{key}' — 下次可直接从 CRM 加载")
        except Exception as e:
            ctx.log(f"CRM enrichment failed (non-fatal): {e}")

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
