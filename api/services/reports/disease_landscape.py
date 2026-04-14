"""
Disease Landscape — third worked example of a ReportService.

Pipeline:
  1. Resolve disease name → CRM enum + search keyword (handles 肿瘤 vs NSCLC)
  2. Query CRM four tables (assets, companies, clinical, deals) with phase ranking
  3. Sample top-N assets prioritising late-stage for prompt budget
  4. Optional Tavily web search (4 queries: guidelines / catalysts / targets / deals)
  5. Single MiniMax call → 8-chapter BD-style landscape report
  6. Save markdown + render styled .docx via docx_builder
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import sqlite3
from typing import Any

from pydantic import BaseModel

from services.helpers import docx_builder, search
from services.helpers.text import format_web_results, safe_slug, search_and_deduplicate

# ── Guidelines DB access ─────────────────────────────────────
_GUIDELINES_DB = os.path.expanduser("~/.openclaw/workspace/guidelines/guidelines.db")


def _guidelines_query(sql: str, params: tuple = ()) -> list[dict]:
    if not os.path.exists(_GUIDELINES_DB):
        return []
    conn = sqlite3.connect(f"file:{_GUIDELINES_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Disease enum mapping (user input → CRM enum)
# ─────────────────────────────────────────────────────────────

DISEASE_ENUM_MAP: dict[str, str] = {
    # Oncology
    "肿瘤": "Oncology", "癌症": "Oncology", "oncology": "Oncology",
    "cancer": "Oncology",
    # Immunology
    "自免": "Immunology", "自身免疫": "Immunology", "免疫": "Immunology",
    "immunology": "Immunology", "autoimmune": "Immunology",
    # Metabolic
    "代谢": "Metabolic", "metabolic": "Metabolic",
    "糖尿病": "Metabolic", "肥胖": "Metabolic", "nash": "Metabolic",
    "diabetes": "Metabolic",
    # Neurology
    "神经": "Neurology", "神经系统": "Neurology",
    "cns": "Neurology", "neurology": "Neurology",
    # Cardiovascular
    "心血管": "Cardiovascular", "心脏": "Cardiovascular",
    "cardiovascular": "Cardiovascular", "cardio": "Cardiovascular",
    # Rare disease
    "罕见病": "Rare Disease", "rare disease": "Rare Disease",
    # Ophthalmology
    "眼科": "Ophthalmology", "眼": "Ophthalmology",
    "ophthalmology": "Ophthalmology",
    # Respiratory
    "呼吸": "Respiratory", "呼吸系统": "Respiratory",
    "respiratory": "Respiratory",
    # Hematology
    "血液": "Hematology", "blood": "Hematology",
    "hematology": "Hematology", "haematology": "Hematology",
    # Infectious
    "感染": "Infectious Disease", "传染病": "Infectious Disease",
    "infectious": "Infectious Disease",
    # Dermatology
    "皮肤": "Dermatology", "dermatology": "Dermatology",
    # GI
    "消化": "Gastroenterology", "胃肠": "Gastroenterology",
    "gi": "Gastroenterology", "gastroenterology": "Gastroenterology",
}


def _resolve_disease(user_input: str) -> tuple[str, str, str]:
    """Map user input to (crm_enum, search_keyword, display_name).

    Returns:
        crm_enum: CRM 疾病领域 enum value, or "" if input is a sub-indication
        search_keyword: Lowercase keyword to match against 适应症 field
        display_name: Title-cased name for report headers

    Logic:
        - If the input matches a known mapping → (enum, "", enum as display)
        - Otherwise treat input as a sub-indication keyword (NSCLC, KRAS G12C, etc.)
          and leave crm_enum empty. The display name keeps the original casing.
    """
    raw = (user_input or "").strip()
    if not raw:
        return "", "", ""

    lower = raw.lower()

    # Direct enum match (with canonical capitalization)
    if lower in DISEASE_ENUM_MAP:
        enum = DISEASE_ENUM_MAP[lower]
        return enum, "", enum

    # Exact enum value (e.g. user typed "Oncology" directly)
    canonical_values = set(DISEASE_ENUM_MAP.values())
    for v in canonical_values:
        if lower == v.lower():
            return v, "", v

    # Sub-indication fallback
    return "", lower, raw


# ─────────────────────────────────────────────────────────────
# Phase ranking — normalise free-text 临床阶段 to numeric order
# ─────────────────────────────────────────────────────────────

def _phase_rank(phase: str | None) -> int:
    """Higher = later stage. Used to prioritise assets when sampling."""
    if not phase:
        return 0
    p = phase.lower()
    if "approved" in p or "commercial" in p or "market" in p or "上市" in phase:
        return 10
    if "nda" in p or "bla" in p:
        return 9
    if "phase 3" in p or "phase iii" in p or "phase3" in p or "p3" in p:
        return 8
    if "phase 2/3" in p:
        return 7
    if "phase 2" in p or "phase ii" in p or "phase2" in p or "p2" in p:
        return 6
    if "phase 1/2" in p:
        return 5
    if "phase 1" in p or "phase i" in p or "phase1" in p or "p1" in p:
        return 4
    if "ind" in p:
        return 3
    if "pre-clinical" in p or "preclinical" in p or "lead" in p:
        return 2
    if "discovery" in p:
        return 1
    return 0


# ─────────────────────────────────────────────────────────────
# Input schema
# ─────────────────────────────────────────────────────────────

class DiseaseLandscapeInput(BaseModel):
    disease: str
    specific_indication: str | None = None
    include_web_search: bool = True
    max_crm_assets: int = 30


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

CHAPTER_SYSTEM_PROMPT = """你是 BD Go 平台的赛道研究主管，正在逐章撰写一份 {disease_display} 赛道竞争格局调研报告。

硬规则：
1. **只写被要求的这一章**，直接输出 markdown，不要加前言或总结
2. **数据说话** — 结论引用 CRM 数据或网络来源，标注 [CRM] 或 [Web]
3. **中美欧三视角** — 覆盖全球格局
4. **表格优于纯文字** — 对比数据必须用表格
5. **洞察优于罗列** — 每章结尾 1-2 句 BD 视角判断（"so what"）
6. **中文为主**，靶点/MOA/机构名保留英文
7. **数据缺失直接说** — 标注 "[CRM 数据稀疏]" 或 "[未获取相关信息]"，不要编造
"""

# ── Chapter prompt templates ──────────────────────────────

_CH1_PROMPT = """
## 任务：撰写第一章 文献综述（目标 ~1200 字）

内容要求：
- 近 2 年重要综述和临床研究（标题+期刊+年份，引用 [Web]）
- 发病机制最新理解与治疗范式变迁
- 中美欧三视角的疾病负担概述

{context_block}

### 前几章要点（上下文连贯性，不要重复）
{running_summary}

直接以 `## 第一章 文献综述` 开头输出 markdown：
"""

_CH2_PROMPT = """
## 任务：撰写第二章 已批准药物（目标 ~1200 字）

内容要求：
- 按机制/代际分类；关键疗效数据（ORR/PFS/OS）；中美欧获批状态和年销售额
- **必须包含表格**：

| 药物名 | 公司 | 靶点/MOA | 获批年份 | 关键数据 | 年销售额($B) |
|---|---|---|---|---|---|

- 段落：治疗范式变迁 + so what

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第二章 已批准药物` 开头输出 markdown：
"""

_CH3_PROMPT = """
## 任务：撰写第三章 在研管线 Phase 3（目标 ~1000 字）

内容要求：
- Phase 3 / NDA / BLA 阶段资产详细分析
- **必须包含表格**：

| 药物名 | 公司 | 靶点-MOA | 阶段 | 差异化 | 关键数据/里程碑 |
|---|---|---|---|---|---|

- 分析：谁是领头羊 + 预计何时获批

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第三章 在研管线（Phase 3 晚期资产）` 开头输出 markdown：
"""

_CH4_PROMPT = """
## 任务：撰写第四章 在研管线 Phase 1/2 + 中国 biotech（目标 ~1000 字）

内容要求：
- Phase 1/2 资产分析；中国 biotech 管线 vs 全球管线对比
- **必须包含表格**：

| 药物名 | 公司 | 靶点-MOA | 阶段 | 国家 | 差异化亮点 |
|---|---|---|---|---|---|

- 黑马候选 + so what

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第四章 在研管线（Phase 1/2 + 中国 biotech）` 开头输出 markdown：
"""

_CH5_PROMPT = """
## 任务：撰写第五章 关键催化剂（目标 ~800 字）

内容要求：
- 未来 24 个月 PDUFA 日期、Phase 3 读出、中国 NMPA 审评、重要学术会议
- **必须包含表格**：

| 预计日期 | 事件 | 公司 | 资产 | BD 含义 |
|---|---|---|---|---|

- 段落：这些催化剂对赛道结构的影响

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第五章 关键催化剂` 开头输出 markdown：
"""

_CH6_PROMPT = """
## 任务：撰写第六章 治疗指南（目标 ~1200 字）

内容要求（**必须使用下方指南数据库数据，不要自行编造**）：
- 分治疗线推荐（一线→二线→三线）
- 生物标志物检测
- US (NCCN) / EU (ESMO) / 中国 (CSCO/CDE) 覆盖
- 指南更新趋势

**必须包含两个表格**：
表格1 — 分治疗线推荐：

| 治疗线 | 推荐等级 | 药物 | 药物类型 | 适应条件 | 疗效概述 | 来源 |
|---|---|---|---|---|---|---|

表格2 — 生物标志物：

| 标志物 | 检测方法 | 阳性阈值 | 临床意义 |
|---|---|---|---|

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第六章 治疗指南` 开头输出 markdown：
"""

_CH7_PROMPT = """
## 任务：撰写第七章 未满足需求（目标 ~1500 字）

内容要求：
- 当前治疗局限（疗效/安全性/可及性/依从性）
- 在研管线覆盖了哪些未满足需求，哪些仍空白
- 患者分层：哪些亚群最缺治疗
- 最大 BD 机会所在

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第七章 未满足需求` 开头输出 markdown：
"""

_CH8_PROMPT = """
## 任务：撰写第八章 新兴靶点 & 技术平台（目标 ~1200 字）

内容要求：
- 近 2 年文献中的新靶点/新机制（标注 [Web]）
- 生信/组学证据（GWAS、proteomics、单细胞测序）
- 有前景的药物模态（ADC/双抗/细胞治疗/基因治疗/mRNA/小分子）
- 平台型公司和技术差异化

{context_block}

### 前几章要点
{running_summary}

直接以 `## 第八章 新兴靶点 & 技术平台` 开头输出 markdown：
"""

_CH9_PROMPT = """
## 任务：撰写第九章 立项评分矩阵（目标 ~1000 字）

内容要求（**基于前八章的具体事实给出量化评分，每个分数必须附一句话依据**）：

**9.1 赛道吸引力评分（6维）**

| 评分维度 | 权重 | 评分(1-5) | 加权分 | 评分依据 |
|---------|------|----------|--------|---------|
| 市场规模 | 20% | /5 | | TAM>$10B=5 |
| 未满足需求 | 25% | /5 | | 严重空白=5 |
| 竞争拥挤度 | 15% | /5 | | 竞品越少越高 |
| 科学成熟度 | 15% | /5 | | 靶点已验证=5 |
| BD交易活跃度 | 15% | /5 | | 近2年>5笔=5 |
| 中国市场机会 | 10% | /5 | | 大量未覆盖患者=5 |
| **赛道总分** | 100% | — | **/5.0** | |

赛道评级：≥4.0 🟢高吸引力 / 3.0-3.9 🟡有选择性机会 / <3.0 🔴吸引力有限

**9.2 资产优先级排名**

| 排名 | 靶点/资产 | 公司 | 阶段 | 科学验证/5 | 差异化/5 | 竞争窗口/5 | 商业潜力/5 | IP空间/5 | 可交易性/5 | 综合/30 | Tier |
|------|---------|------|------|-----------|---------|-----------|-----------|---------|-----------|--------|------|

Tier 1(≥25): 立刻启动 | Tier 2(20-24): 重点关注 | Tier 3(15-19): 机会性 | Tier 4(<15): 不建议

**9.3 BD 后续行动清单**（P0/P1/P2 优先级，具体资产/靶点，建议时限）

### 所有前章要点（评分依据来源）
{running_summary}

直接以 `## 第九章 立项评分矩阵` 开头输出 markdown：
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────

class DiseaseLandscapeService(ReportService):
    slug = "disease-landscape"
    display_name = "Disease Landscape"
    description = (
        "\u8d5b\u9053\u7ade\u4e89\u683c\u5c40\u6df1\u5ea6\u8c03\u7814\u3002"
        "CRM \u56db\u8868\u4ea4\u53c9\u67e5\u8be2 + Tavily \u7f51\u7edc\u68c0\u7d22\uff0c"
        "\u8f93\u51fa 8 \u7ae0\u8282\u7684 Word \u8d5b\u9053\u62a5\u544a\uff08\u5df2\u6279\u51c6\u3001\u5728\u7814\u7ba1\u7ebf\u3001\u50ac\u5316\u5242\u3001\u6307\u5357\u3001"
        "\u672a\u6ee1\u8db3\u9700\u6c42\u3001\u65b0\u5174\u9776\u70b9\u3001\u6280\u672f\u5e73\u53f0\u3001BD \u542f\u793a\uff09\u3002"
    )
    chat_tool_name = "research_disease"
    chat_tool_description = (
        "Generate a BD-focused competitive landscape report for a disease or therapeutic area. "
        "Accepts broad categories (Oncology, Metabolic, Neurology) or specific sub-indications "
        "(NSCLC, NASH, KRAS G12C). Queries CRM assets/trials/deals + optional web search for "
        "guidelines and recent readouts. Returns an 8-chapter Word document (~3500 words, 120-180s)."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "disease": {
                "type": "string",
                "description": "Disease or therapeutic area. Accepts broad categories ('Oncology', '\u80bf\u7624', 'Metabolic') or sub-indications ('NSCLC', 'NASH', 'KRAS G12C').",
            },
            "specific_indication": {
                "type": "string",
                "description": "Optional: further narrow the report to a specific sub-indication while keeping the broad disease category (e.g. disease='Oncology', specific_indication='KRAS G12C NSCLC').",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Augment with Tavily web search for guidelines, readouts, and recent deals (default true).",
                "default": True,
            },
            "max_crm_assets": {
                "type": "integer",
                "description": "Cap on number of CRM assets to feed into the LLM prompt (default 30, range 10-60). Reports covering huge categories like Oncology rely on late-stage sampling.",
                "default": 30,
            },
        },
        "required": ["disease"],
    }
    input_model = DiseaseLandscapeInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 600
    category = "research"
    field_rules = {}

    # ── main run ────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DiseaseLandscapeInput(**params)
        max_assets = max(10, min(inp.max_crm_assets, 60))

        # Phase 1: Resolve disease → enum + keyword
        enum, keyword, display = _resolve_disease(inp.disease)
        if inp.specific_indication:
            keyword = inp.specific_indication.strip().lower()
            display = f"{display} — {inp.specific_indication}"
        if not enum and not keyword:
            raise ValueError("Could not resolve disease input. Try 'Oncology', 'NSCLC', 'NASH', etc.")

        ctx.log(f"Resolved: enum={enum or '(sub-indication mode)'} keyword={keyword or '(none)'}")

        # Phase 2: CRM queries
        ctx.log("Querying CRM four tables...")
        assets = self._query_assets(ctx, enum, keyword, max_assets)
        companies = self._query_companies(ctx, enum, keyword)
        trials = self._query_clinical(ctx, keyword, limit=20)
        deals = self._query_deals(ctx, keyword, limit=10)
        guidelines_recs = _guidelines_query(
            '''SELECT r."治疗线", r."推荐等级", r."证据级别", r."药物", r."药物类型",
                      r."适应条件", r."疗效概述", g."指南来源", g."版本"
               FROM "推荐" r JOIN "指南" g ON r."指南ID" = g."记录ID"
               WHERE g."疾病" LIKE ?
               ORDER BY r."治疗线", r."推荐等级"
               LIMIT 30''',
            (f"%{keyword or enum}%",),
        )
        guidelines_biomarkers = _guidelines_query(
            'SELECT "标志物", "检测方法", "阳性阈值", "临床意义" FROM "生物标志物" WHERE "疾病" LIKE ? LIMIT 20',
            (f"%{keyword or enum}%",),
        )
        ctx.log(
            f"CRM: {len(assets)} assets, {len(companies)} companies, "
            f"{len(trials)} trials, {len(deals)} deals | "
            f"Guidelines: {len(guidelines_recs)} recs, {len(guidelines_biomarkers)} biomarkers"
        )

        # Phase 2b: Web search
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Running Tavily web searches (4 queries)...")
            web_results = self._run_web_searches(display, enum, keyword)
            ctx.log(f"Web search returned {len(web_results)} unique results")
        else:
            ctx.log("Web search disabled — CRM-only mode")

        # Pre-format shared data blocks
        assets_block = self._format_assets(assets)
        companies_block = self._format_companies(companies)
        trials_block = self._format_trials(trials)
        deals_block = self._format_deals(deals)
        guidelines_block = self._format_guidelines(guidelines_recs, guidelines_biomarkers)
        web_block = format_web_results(web_results, inp.include_web_search)
        today = datetime.date.today().isoformat()

        # Shared context block injected into every chapter prompt
        shared_context = (
            f"**疾病**: {display} | **日期**: {today}\n\n"
            f"**资产数据** ({len(assets)} 个，按阶段优先级):\n{assets_block}\n\n"
            f"**公司数据** ({len(companies)} 家):\n{companies_block}\n\n"
            f"**临床试验** ({len(trials)} 条):\n{trials_block}\n\n"
            f"**交易数据** ({len(deals)} 笔):\n{deals_block}\n\n"
            f"**指南数据**:\n{guidelines_block}\n\n"
            f"**网络检索结果**:\n{web_block}"
        )

        system_prompt = CHAPTER_SYSTEM_PROMPT.format(disease_display=display)

        # Phase 3: Generate chapters one by one
        chapter_texts: dict[int, str] = {}
        running_summary = ""

        # ── Chapter 1: 文献综述 ──
        ctx.log("第一章：文献综述...")
        ch1_prompt = _CH1_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary or "(无，这是第一章)",
        )
        chapter_texts[1] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch1_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第一章 文献综述要点】{chapter_texts[1][:800]}"
        ctx.log(f"第一章完成（{len(chapter_texts[1])}字）")

        # ── Chapter 2: 已批准药物 ──
        ctx.log("第二章：已批准药物...")
        ch2_prompt = _CH2_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[2] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch2_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第二章 已批准药物要点】{chapter_texts[2][:800]}"
        ctx.log(f"第二章完成（{len(chapter_texts[2])}字）")

        # ── Chapter 3: 在研管线 Phase 3 ──
        ctx.log("第三章：在研管线 Phase 3...")
        ch3_prompt = _CH3_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[3] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch3_prompt}],
            max_tokens=2200,
        )
        running_summary += f"\n\n【第三章 Phase 3管线要点】{chapter_texts[3][:600]}"
        ctx.log(f"第三章完成（{len(chapter_texts[3])}字）")

        # ── Chapter 4: 在研管线 Phase 1/2 + 中国 biotech ──
        ctx.log("第四章：在研管线 Phase 1/2 + 中国 biotech...")
        ch4_prompt = _CH4_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[4] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch4_prompt}],
            max_tokens=2200,
        )
        running_summary += f"\n\n【第四章 早期管线要点】{chapter_texts[4][:600]}"
        ctx.log(f"第四章完成（{len(chapter_texts[4])}字）")

        # ── Chapter 5: 关键催化剂 ──
        ctx.log("第五章：关键催化剂...")
        ch5_prompt = _CH5_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[5] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch5_prompt}],
            max_tokens=1800,
        )
        running_summary += f"\n\n【第五章 催化剂要点】{chapter_texts[5][:500]}"
        ctx.log(f"第五章完成（{len(chapter_texts[5])}字）")

        # ── Chapter 6: 治疗指南 ──
        ctx.log("第六章：治疗指南...")
        ch6_prompt = _CH6_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[6] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch6_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第六章 治疗指南要点】{chapter_texts[6][:500]}"
        ctx.log(f"第六章完成（{len(chapter_texts[6])}字）")

        # ── Chapter 7: 未满足需求 ──
        ctx.log("第七章：未满足需求...")
        ch7_prompt = _CH7_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[7] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch7_prompt}],
            max_tokens=3000,
        )
        running_summary += f"\n\n【第七章 未满足需求要点】{chapter_texts[7][:600]}"
        ctx.log(f"第七章完成（{len(chapter_texts[7])}字）")

        # ── Chapter 8: 新兴靶点 & 技术平台 ──
        ctx.log("第八章：新兴靶点 & 技术平台...")
        ch8_prompt = _CH8_PROMPT.format(
            context_block=shared_context,
            running_summary=running_summary[-1000:],
        )
        chapter_texts[8] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch8_prompt}],
            max_tokens=2500,
        )
        running_summary += f"\n\n【第八章 新兴靶点要点】{chapter_texts[8][:500]}"
        ctx.log(f"第八章完成（{len(chapter_texts[8])}字）")

        # ── Chapter 9: 立项评分矩阵 ──
        ctx.log("第九章：立项评分矩阵...")
        ch9_prompt = _CH9_PROMPT.format(
            running_summary=running_summary[-1000:],
        )
        chapter_texts[9] = ctx.llm(
            system=system_prompt,
            messages=[{"role": "user", "content": ch9_prompt}],
            max_tokens=2500,
        )
        ctx.log(f"第九章完成（{len(chapter_texts[9])}字）")

        # Phase 4: Merge chapters + header
        header = (
            f"# {display} 赛道竞争格局调研\n\n"
            f"> **生成日期**: {today} | **分析师**: BD Go (赛道研究) | "
            f"**数据源**: CRM ({len(assets)} 个资产, {len(trials)} 条临床, "
            f"{len(deals)} 笔交易) + Tavily Web Search\n\n"
        )
        markdown = header + "\n\n".join(chapter_texts[i] for i in range(1, 10))

        total_chars = len(markdown)
        ctx.log(f"全部 9 章合并完成，总计约 {total_chars} 字")

        if total_chars < 1000:
            raise RuntimeError("LLM returned empty or very short report")

        # Phase 4b: Save markdown + render docx
        slug = safe_slug(display)
        md_filename = f"disease_landscape_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=display,
            subtitle="Disease Landscape Report",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)

        docx_filename = f"disease_landscape_{slug}.docx"
        ctx.save_file(docx_filename, docx_bytes, format="docx")
        ctx.log("Word document saved")

        return ReportResult(
            markdown=markdown,
            meta={
                "disease": inp.disease,
                "display": display,
                "enum": enum,
                "keyword": keyword,
                "n_assets": len(assets),
                "n_companies": len(companies),
                "n_trials": len(trials),
                "n_deals": len(deals),
                "web_results_count": len(web_results),
                "chapters": 9,
                "total_chars": total_chars,
            },
        )

    # ── CRM queries ─────────────────────────────────────────
    def _query_assets(self, ctx: ReportContext, enum: str, keyword: str, limit: int) -> list[dict]:
        """Fetch assets matching disease area or indication keyword, sample by phase rank."""
        conds: list[str] = []
        params: list[Any] = []
        if enum:
            conds.append('"疾病领域" LIKE ?')
            params.append(f"%{enum}%")
        if keyword:
            conds.append('("适应症" LIKE ? OR "靶点" LIKE ? OR "作用机制(MOA)" LIKE ?)')
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        if not conds:
            return []

        where = " OR ".join(conds) if len(conds) > 1 else conds[0]
        sql = (
            'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
            '"疾病领域", "适应症", "差异化分级", "差异化描述", "Q总分", "技术平台类别", '
            '"下一个临床节点", "节点预计时间" '
            f'FROM "资产" WHERE {where} LIMIT 300'
        )
        rows = ctx.crm_query(sql, tuple(params))

        # Rank in Python (phase ranking is non-trivial in SQL)
        rows.sort(key=lambda r: _phase_rank(r.get("临床阶段")), reverse=True)
        if len(rows) > limit:
            ctx.log(f"Sampled {limit} of {len(rows)} assets (late-stage priority)")
        return rows[:limit]

    def _query_companies(self, ctx: ReportContext, enum: str, keyword: str) -> list[dict]:
        conds: list[str] = []
        params: list[Any] = []
        if enum:
            conds.append('"疾病领域" LIKE ?')
            params.append(f"%{enum}%")
        if keyword:
            conds.append('("疾病领域" LIKE ? OR "核心产品的阶段" LIKE ? OR "主要核心pipeline的名字" LIKE ?)')
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        if not conds:
            return []
        where = " OR ".join(conds) if len(conds) > 1 else conds[0]
        sql = (
            'SELECT "客户名称", "客户类型", "所处国家", "核心产品的阶段", '
            '"主要核心pipeline的名字", "BD跟进优先级" '
            f'FROM "公司" WHERE {where} LIMIT 20'
        )
        return ctx.crm_query(sql, tuple(params))

    def _query_clinical(self, ctx: ReportContext, keyword: str, limit: int = 20) -> list[dict]:
        if not keyword:
            return []
        sql = (
            'SELECT "试验ID", "资产名称", "公司名称", "适应症", "临床期次", '
            '"主要终点名称", "主要终点结果值", "结果判定", "临床综合评分" '
            'FROM "临床" '
            'WHERE "适应症" LIKE ? '
            'ORDER BY "评估日期" DESC '
            'LIMIT ?'
        )
        return ctx.crm_query(sql, (f"%{keyword}%", limit))

    def _query_deals(self, ctx: ReportContext, keyword: str, limit: int = 10) -> list[dict]:
        if not keyword:
            return []
        sql = (
            'SELECT "交易名称", "交易类型", "买方公司", "卖方/合作方", "资产名称", '
            '"靶点", "临床阶段", "首付款($M)", "交易总额($M)", "宣布日期" '
            'FROM "交易" '
            'WHERE "适应症" LIKE ? OR "靶点" LIKE ? '
            'ORDER BY "宣布日期" DESC '
            'LIMIT ?'
        )
        return ctx.crm_query(sql, (f"%{keyword}%", f"%{keyword}%", limit))

    # ── web search ──────────────────────────────────────────
    def _run_web_searches(self, display: str, enum: str, keyword: str) -> list[dict]:
        # Prefer English term for web search (better results from Tavily)
        term = enum or keyword or display
        queries = [
            f"{term} treatment landscape guidelines NCCN ESMO 2025 2026",
            f"{term} Phase 3 clinical readout PDUFA 2026",
            f"{term} novel target mechanism emerging 2025",
            f"{term} BD deal licensing acquisition 2025 2026",
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
    def _format_assets(self, assets: list[dict]) -> str:
        if not assets:
            return "(\u65e0\u5339\u914d\u7684 CRM \u8d44\u4ea7)"
        lines = []
        # Group by phase for readability
        by_stage: dict[str, list[dict]] = {}
        for a in assets:
            stage = a.get("临床阶段") or "(unknown)"
            by_stage.setdefault(stage, []).append(a)
        # Sort stages by rank descending
        sorted_stages = sorted(by_stage.keys(), key=lambda s: _phase_rank(s), reverse=True)
        for stage in sorted_stages:
            lines.append(f"### {stage} ({len(by_stage[stage])})")
            for a in by_stage[stage]:
                name = a.get("资产名称") or "(unnamed)"
                company = a.get("所属客户") or "-"
                target = a.get("靶点") or "-"
                moa = a.get("作用机制(MOA)") or "-"
                ind = a.get("适应症") or "-"
                diff = a.get("差异化分级") or ""
                q = a.get("Q总分") or ""
                extra = f" [Q={q}]" if q else ""
                lines.append(f"- **{name}** ({company}) | {target} | {moa} | {ind}{extra} {diff}")
        return "\n".join(lines)

    def _format_companies(self, companies: list[dict]) -> str:
        if not companies:
            return "(\u65e0)"
        return "\n".join(
            f"- {c.get('客户名称','?')} ({c.get('所处国家','?')}) | {c.get('客户类型','?')} | "
            f"stage={c.get('核心产品的阶段','-')} | pipeline={c.get('主要核心pipeline的名字','-')}"
            for c in companies
        )

    def _format_trials(self, trials: list[dict]) -> str:
        if not trials:
            return "(\u65e0)"
        return "\n".join(
            f"- {t.get('试验ID','?')}: {t.get('资产名称','?')} ({t.get('公司名称','?')}) | "
            f"{t.get('适应症','-')} | {t.get('临床期次','-')} | 终点={t.get('主要终点名称','-')} "
            f"{t.get('主要终点结果值','')} | 判定={t.get('结果判定','-')} | Score={t.get('临床综合评分','-')}"
            for t in trials
        )

    def _format_deals(self, deals: list[dict]) -> str:
        if not deals:
            return "(\u65e0)"
        return "\n".join(
            f"- [{d.get('宣布日期','?')}] {d.get('交易名称','?')} | {d.get('交易类型','?')} | "
            f"Buyer: {d.get('买方公司','?')} ← Seller: {d.get('卖方/合作方','?')} | "
            f"Asset: {d.get('资产名称','-')} ({d.get('靶点','-')}, {d.get('临床阶段','-')}) | "
            f"Upfront: ${d.get('首付款($M)','-')}M | Total: ${d.get('交易总额($M)','-')}M"
            for d in deals
        )

    def _format_guidelines(self, recs: list[dict], biomarkers: list[dict]) -> str:
        parts = []
        if recs:
            parts.append(f"**治疗推荐** ({len(recs)} 条):")
            for r in recs:
                parts.append(
                    f"- [{r.get('治疗线','-')}] {r.get('推荐等级','-')}/{r.get('证据级别','-')} "
                    f"**{r.get('药物','-')}** ({r.get('药物类型','')}) | "
                    f"条件:{r.get('适应条件','')} | 疗效:{r.get('疗效概述','')} | "
                    f"来源:{r.get('指南来源','')} {r.get('版本','')}"
                )
        else:
            parts.append("(指南数据库中无该疾病的推荐数据)")

        if biomarkers:
            parts.append(f"\n**生物标志物** ({len(biomarkers)} 条):")
            for b in biomarkers:
                parts.append(
                    f"- **{b.get('标志物','?')}** | 方法:{b.get('检测方法','-')} | "
                    f"阈值:{b.get('阳性阈值','-')} | 意义:{b.get('临床意义','-')}"
                )

        return "\n".join(parts) if parts else "(无指南数据)"

    # ── helpers ─────────────────────────────────────────────
