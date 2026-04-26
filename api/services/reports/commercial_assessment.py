# MIRROR OF: ~/.openclaw/skills/commercial-assessment/SKILL.md (synced 2026-04-15)
# Sync prompts FROM SKILL.md, not the other way. See docs/SKILL_MIRROR.md.

"""
Commercial Assessment — market sizing, pricing, and launch strategy report.

Scoped port of the @商业化 OpenClaw skill for the BD Go web platform.
Produces a ~4000-word Word report covering:

  1. Executive Summary & 商业化评级矩阵
  2. 患者漏斗 & 市场规模 (TAM/SAM/SOM)
  3. 竞品定价格局
  4. 市场准入 & 支付方分析
  5. 商业化路径 & 资源估算
  6. SWOT & 风险
  7. Revenue Forecast (三情景)

Input: asset_name + optional company, target, indication.
Data: CRM assets/deals + optional Tavily web search.
"""

from __future__ import annotations

import datetime
import logging

from crm_store import LIKE_ESCAPE, like_contains
from pydantic import BaseModel

from services.document import docx_builder
from services.quality import audit_to_dict, validate_markdown
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import format_web_results, safe_slug, search_and_deduplicate

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class CommercialAssessmentInput(BaseModel):
    asset_name: str  # Drug / asset name or target keyword
    company: str | None = None  # Developer company name (optional)
    indication: str | None = None  # Specific indication (optional)
    target: str | None = None  # Target / MOA keyword (optional)
    include_web_search: bool = True


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 BD Go 平台的商业化评估专家。你的任务：基于 CRM 数据 + 外部检索，
为指定管线资产撰写一份面向 BD 决策者的商业化潜力评估报告。

核心问题：**这个资产如果成功上市，能赚多少钱、怎么赚？BD 交易定价应该参考什么？**

硬规则：
1. **每个数字标来源** — 格式：[BDGO] / [Web] / [行业基准⚠️]
2. **患者漏斗必须逐层递减** — 每层 ≤ 上层，比率必须 0-100%
3. **Peak Revenue 三情景** — 保守/基准/乐观，给 range 不给点估计
4. **分地区分析** — US / 中国 / EU5 三个市场，准入逻辑不同
5. **不做 DCF 折现** — 只做 Revenue Forecast，不算 NPV/WACC
6. **竞品定价必须有** — 至少 3 个竞品的定价对标
7. **表格优于纯文字** — 患者漏斗、竞品对比、Revenue 预测必须用表格
8. **中文为主**，药物名/靶点/MOA 保留英文
9. **数据稀疏直接说** — 标 [CRM 数据稀疏] 或 [未获取相关信息]，不要编造
10. **严格按 7 章输出**，直接输出 markdown，不要前言
"""

REPORT_PROMPT = """以下是 **{asset_display}** 的商业化评估数据。
请按 7 章结构撰写一份 ~4000 字的商业化潜力评估报告。

═════════════════════════════════════════════
## CRM 数据
═════════════════════════════════════════════

**目标资产** ({n_target} 个):
{target_block}

**同领域竞品** ({n_competitors} 个，按阶段排序):
{competitors_block}

**可比交易** ({n_deals} 笔，按日期倒序):
{deals_block}

═════════════════════════════════════════════
## 网络检索结果
═════════════════════════════════════════════
{web_block}

═════════════════════════════════════════════
## 输出格式
═════════════════════════════════════════════

严格按下面的 markdown 模板输出（直接开始，不要加前言）：

```
# {asset_display} 商业化潜力评估

> **生成日期**: {today} | **分析师**: BD Go (商业化评估) | **数据源**: CRM + Web Search

---

## 第1章 执行摘要 & 商业化评级

### 商业化评级矩阵

| 评估维度 | 评级 | 评分(1-5) | 核心判断 |
|---------|------|----------|---------|
| 市场规模 | 大/中/小 | /5 | （一句话依据）|
| 定价空间 | 高/中/低 | /5 | |
| 竞争强度 | 弱/中/强 | /5 | |
| 准入难度 | 易/中/难 | /5 | |
| 差异化程度 | 强/中/弱 | /5 | |
| **综合评级** | | **/25** | 🟢可期/🟡中等/🔴挑战 |

（评分标准：🟢≥20 商业化前景优秀 / 🟡15-19 可行但有挑战 / 🔴<15 挑战大）

### Peak Revenue 速览

| 情景 | Peak Revenue | 达峰时间 | 核心假设 |
|------|-------------|---------|---------|
| 🐻 保守 | $X M | Year X | （低渗透率+强竞争）|
| 📊 基准 | $X M | Year X | （中间假设）|
| 🐂 乐观 | $X M | Year X | （Best-in-class+适应症扩展）|

（一句话商业化结论：这个资产的天花板是什么，最大风险是什么）

---

## 第2章 患者漏斗 & 市场规模

### 患者漏斗（Patient Funnel）

| 漏斗层级 | US | 中国 | EU5 | 数据来源 |
|---------|----|----|-----|---------|
| 总人口 | 330M | 1,400M | 330M | |
| 患病/发病人数 | | | | [来源] |
| × 确诊率 | | | | |
| = 确诊患者 | | | | |
| × 治疗合格率 | | | | |
| = 治疗合格患者 | | | | |
| × 目标线数份额 | | | | |
| = 可及患者(Addressable) | | | | |

（说明各层比率假设的依据）

### TAM / SAM / SOM

| 层级 | 定义 | 金额 | 计算逻辑 |
|------|------|------|---------|
| TAM | 所有确诊患者 × 年治疗费 | $X B | |
| SAM | 可及患者 × 年治疗费 | $X B | |
| SOM | 可及患者 × 渗透率 × 年治疗费 | $X M | |

（市场增长驱动力分析：患病率趋势、诊断率改善、中国增量机会）

---

## 第3章 竞品定价格局

### 竞品定价对标

| 竞品药物 | 公司 | 靶点/MOA | 阶段 | US年费($) | 中国年费(¥) | 年销售额($M) |
|---------|------|---------|------|----------|------------|------------|
| ... | | | | | | [来源] |

### 定价策略分析

**US 定价**（参考区间、定价依据、Gross-to-Net~45%、净价）

**中国定价**（国谈前/后价格、同类降幅、医保报销比例）

**EU5 定价**（US价格的60-70%，HTA要求）

### 渗透率预测

| 阶段 | 渗透率（占峰值%） | 逻辑 |
|------|----------------|------|
| Launch Year | ~10% | 初始采用 |
| Y3 | ~45% | 快速爬坡 |
| Y5 | ~80% | 接近峰值 |
| Y7+ | ~95-100% | 峰值维持 |
| LOE后 | 每年-30%(小分子)/-15%(生物) | 仿制侵蚀 |

（竞争动态：SOC差异化、未来3年竞品、颠覆性技术、仿制药威胁时间线）

---

## 第4章 市场准入 & 支付方

### US 准入
（Medicare覆盖 Part B/D、商业保险 Prior Auth 要求、Specialty pharmacy、患者自付）

### 中国准入
（NMPA审批路径、医保国谈概率、参考同类降幅、DRG/DIP影响、院内院外双通道）

### EU5 准入
（NICE/G-BA/HAS/AIFA/AEMPS评估要点）

### 准入风险总结

| 市场 | 准入难度 | 核心风险 | 预计准入时间（获批后）|
|------|---------|---------|------------------|
| US | | | |
| 中国 | | | |
| EU5 | | | |

---

## 第5章 商业化路径 & 资源估算

### Launch 策略

| 阶段 | 时间线 | 关键活动 |
|------|--------|---------|
| Pre-launch (获批前24月) | Y-2 to Y0 | KOL engagement, MSL部署 |
| Launch | Y0 to Y1 | 销售团队, 学术推广 |
| Growth | Y1 to Y5 | 扩大覆盖, 新适应症 |

### 商业化资源估算（基准情景）

| 资源项 | US | 中国 |
|--------|----|----|
| 销售团队规模 | X reps @ $280K | X人 |
| MSL团队 | X人 @ $350K | X人 |
| 年度市场推广 | $X M | ¥X M |
| Launch年总投入 | $X M | ¥X M |
| 商业化期 SG&A（占Net Revenue%） | ~25% | ~20% |

---

## 第6章 SWOT & 关键风险

| | 正面 | 负面 |
|---|------|------|
| **内部** | **Strengths**（差异化、数据、IP）| **Weaknesses**（临床局限、CMC风险）|
| **外部** | **Opportunities**（市场空白、中国增量、适应症扩展）| **Threats**（竞品、仿制药、医保降价）|

### 关键风险与缓解

| 风险类别 | 具体风险 | 概率 | 影响 | 缓解措施 |
|---------|---------|------|------|---------|
| 竞争风险 | | 高/中/低 | 高/中/低 | |
| 准入风险 | | | | |
| 定价风险 | | | | |
| 执行风险 | | | | |

---

## 第7章 Revenue Forecast & BD 启示

### 基准情景 Peak Revenue 推导

```
Peak Revenue = Addressable Patients × Net Price × Peak Penetration

US:     X patients × $X/年 × X% = $X M
中国:    X patients × ¥X/年 × X% = $X M (≈ $X M)
EU5:    X patients × $X/年 × X% = $X M
RoW:    US+EU的15-20%
─────────────────────────────────────────
全球 Peak Revenue（基准）: $X M
```

### 三情景汇总

| 情景 | Peak Revenue | 达峰年 | 关键假设差异 |
|------|-------------|--------|------------|
| 🐻 保守 | $X M | Year X | 低渗透+强竞争+低定价 |
| 📊 基准 | $X M | Year X | 中间假设 |
| 🐂 乐观 | $X M | Year X | 高渗透+差异化溢价+适应症扩展 |

### 交易对标参考

| 对标交易 | 资产阶段 | 买方 | 交易金额 | 首付 | Implied Peak Sales |
|---------|---------|------|---------|------|-------------------|
| （来自 CRM 交易数据） | | | | | |

### BD 决策建议

（3-4 句话：商业化天花板、最大商业化风险、对BD交易定价的启示、建议后续行动）
```

**最后提醒**：直接开始输出 markdown，不加任何前言。"""


# ─────────────────────────────────────────────────────────────
# Phase ranking helper
# ─────────────────────────────────────────────────────────────


def _phase_rank(phase: str | None) -> int:
    if not phase:
        return 0
    p = phase.lower()
    if any(x in p for x in ["approved", "commercial", "market", "上市"]):
        return 10
    if any(x in p for x in ["nda", "bla"]):
        return 9
    if "phase 3" in p or "phase iii" in p or "phase3" in p:
        return 8
    if "phase 2/3" in p:
        return 7
    if "phase 2" in p or "phase ii" in p or "phase2" in p:
        return 6
    if "phase 1/2" in p:
        return 5
    if "phase 1" in p or "phase i" in p or "phase1" in p:
        return 4
    return 2


_GAP_FILL_PROMPT = """以下是已生成的商业化评估 Markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验的内容**的前提下，仅修补以下缺陷，输出完整的修正后 Markdown（从第一行到最后一行）。

=== 待修补缺陷 ===
{fail_list}

=== 原始 Markdown ===
{markdown}

修补规则：
- 每条缺陷注明了章节（section）和问题描述（message），只修改相关章节
- 如果缺陷是"字数不足"，在该章节末尾补充内容，保持同一标题下
- 如果缺陷是"小节缺失"，在父章节末尾插入该小节及占位内容（≥150字）
- 不要添加新章节、不要删除已有内容、不要改标题格式
- 输出整个 Markdown，不加任何解释或代码块包裹
"""


def _build_gap_fill_prompt(markdown: str, audit) -> str:
    fail_lines = [
        f"[{f.section}] {f.message}" + (f" | 证据: {f.evidence}" if f.evidence else "")
        for f in audit.findings
        if f.severity == "fail"
    ]
    return _GAP_FILL_PROMPT.format(
        fail_list="\n".join(f"- {line}" for line in fail_lines),
        markdown=markdown[:60_000],
    )


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class CommercialAssessmentService(ReportService):
    slug = "commercial-assessment"
    display_name = "Commercial Assessment"
    description = (
        "资产商业化潜力评估：市场规模（患者漏斗/TAM/SAM/SOM）、竞品定价、"
        "市场准入、商业化路径、三情景 Revenue Forecast（~4000字 Word 报告）。"
    )
    chat_tool_name = "analyze_commercial"
    chat_tool_description = (
        "Generate a commercial assessment report for a pipeline asset. "
        "Covers patient funnel, market sizing (TAM/SAM/SOM), competitor pricing, "
        "reimbursement access (US/China/EU), launch strategy, and 3-scenario revenue forecast. "
        "Output: ~4000-word Word document (150-200s). "
        "Use when user asks about commercial potential, market size, peak sales, pricing strategy, "
        "or '商业化评估', '市场规模', 'peak sales', '这个药能卖多少'."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "asset_name": {
                "type": "string",
                "description": "Drug/asset name, target, or company keyword. E.g. 'QL1706', 'PD-1', 'BeiGene ADC'.",
            },
            "company": {
                "type": "string",
                "description": "Developer company name (optional, helps narrow search).",
            },
            "indication": {
                "type": "string",
                "description": "Target indication, e.g. 'NSCLC', 'SLE', 'HER2+ breast cancer' (optional).",
            },
            "target": {
                "type": "string",
                "description": "Target or MOA keyword, e.g. 'PD-1', 'KRAS G12C', 'ADC' (optional).",
            },
            "include_web_search": {
                "type": "boolean",
                "description": "Augment with Tavily web search for epidemiology, pricing, and reimbursement data (default true).",
                "default": True,
            },
        },
        "required": ["asset_name"],
    }
    input_model = CommercialAssessmentInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 180
    category = "research"
    field_rules = {}

    # ── main run ────────────────────────────────────────────
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = CommercialAssessmentInput(**params)

        # Build display name
        parts = [inp.asset_name]
        if inp.company:
            parts.append(f"({inp.company})")
        if inp.indication:
            parts.append(f"/ {inp.indication}")
        asset_display = " ".join(parts)

        ctx.log(f"Commercial assessment for: {asset_display}")

        # 1. CRM queries
        ctx.log("Querying CRM assets (target + competitors)...")
        target_assets, competitors = self._query_assets(ctx, inp)

        ctx.log("Querying CRM deals (comparables)...")
        deals = self._query_deals(ctx, inp)

        ctx.log(
            f"CRM: {len(target_assets)} target assets, "
            f"{len(competitors)} competitors, {len(deals)} deals"
        )

        # 2. Web search
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Running Tavily web searches (6 queries)...")
            web_results = self._run_web_searches(inp, asset_display)
            ctx.log(f"Web search: {len(web_results)} unique results")
        else:
            ctx.log("Web search disabled")

        # 3. Build prompt + LLM call
        ctx.log("Generating 7-chapter commercial assessment via LLM...")
        prompt = REPORT_PROMPT.format(
            asset_display=asset_display,
            today=datetime.date.today().isoformat(),
            n_target=len(target_assets),
            n_competitors=len(competitors),
            n_deals=len(deals),
            target_block=self._format_assets(target_assets),
            competitors_block=self._format_assets(competitors),
            deals_block=self._format_deals(deals),
            web_block=format_web_results(web_results, inp.include_web_search),
        )

        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
        )

        if not markdown or len(markdown.strip()) < 300:
            raise RuntimeError("LLM returned empty or very short report")

        # 4. Save markdown + docx
        slug = safe_slug(asset_display)
        md_filename = f"commercial_assessment_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=asset_display,
            subtitle="Commercial Assessment Report",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)

        docx_filename = f"commercial_assessment_{slug}.docx"
        ctx.save_file(docx_filename, docx_bytes, format="docx")
        ctx.log("Word document saved")

        # Phase 5: Schema validation + L1 gap-fill retry
        schema_audit: dict = {}
        gap_fill_attempted = False
        try:
            audit = validate_markdown(markdown, mode="commercial_biotech")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")

            if audit.n_fail > 0:
                ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — retrying targeted patch...")
                gap_fill_attempted = True
                patched = ctx.llm(
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                    max_tokens=8000,
                    label="commercial_gap_fill",
                )
                if patched and len(patched.strip()) > 500:
                    markdown = patched
                    audit2 = validate_markdown(markdown, mode="commercial_biotech")
                    ctx.log(
                        f"Post-gap-fill audit: FAIL={audit2.n_fail} WARN={audit2.n_warn}"
                        f" (was {audit.n_fail} fail)"
                    )
                    schema_audit = audit_to_dict(audit2)
                    schema_audit["gap_fill_attempted"] = True
                    schema_audit["gap_fill_fail_before"] = audit.n_fail
                    schema_audit["gap_fill_fail_after"] = audit2.n_fail

                    ctx.save_file(md_filename, markdown, format="md")
                    doc2 = docx_builder.new_report_document()
                    docx_builder.add_title(
                        doc2, title=asset_display, subtitle="Commercial Assessment Report"
                    )
                    docx_builder.markdown_to_docx(markdown, doc2)
                    ctx.save_file(
                        docx_filename, docx_builder.document_to_bytes(doc2), format="docx"
                    )
                    ctx.log("Gap-filled md + docx re-saved")
                else:
                    ctx.log("L1 gap-fill returned empty response — keeping original")
                    schema_audit = audit_to_dict(audit)
                    schema_audit["gap_fill_attempted"] = True
                    schema_audit["gap_fill_fail_before"] = audit.n_fail
            else:
                schema_audit = audit_to_dict(audit)
        except Exception:
            logger.exception("Schema validation failed for task %s", ctx.task_id)
            schema_audit = {
                "error": "validator_exception",
                "gap_fill_attempted": gap_fill_attempted,
            }

        return ReportResult(
            markdown=markdown,
            meta={
                "asset_name": inp.asset_name,
                "company": inp.company,
                "indication": inp.indication,
                "display": asset_display,
                "n_target_assets": len(target_assets),
                "n_competitors": len(competitors),
                "n_deals": len(deals),
                "web_results_count": len(web_results),
                "chapters": 7,
                "schema_audit": schema_audit,
            },
        )

    # ── CRM queries ─────────────────────────────────────────
    def _query_assets(
        self, ctx: ReportContext, inp: CommercialAssessmentInput
    ) -> tuple[list[dict], list[dict]]:
        """Return (target_assets, competitors)."""
        kw = inp.asset_name.lower()
        company_kw = (inp.company or "").lower()
        target_kw = (inp.target or "").lower()
        indication_kw = (inp.indication or "").lower()

        sql = (
            'SELECT "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", '
            '"疾病领域", "适应症", "差异化分级", "差异化描述", "峰值销售预测", '
            '"竞品情况" '
            'FROM "资产" LIMIT 500'
        )
        all_rows = ctx.crm_query(sql, ())

        target_assets: list[dict] = []
        competitors: list[dict] = []
        for r in all_rows:
            name = (r.get("资产名称") or "").lower()
            company = (r.get("所属客户") or "").lower()
            tgt = (r.get("靶点") or "").lower()
            ind = (r.get("适应症") or "").lower()

            is_target = (
                kw in name
                or (company_kw and company_kw in company)
                or (target_kw and target_kw in tgt and indication_kw and indication_kw in ind)
            )
            is_competitor = not is_target and (
                (target_kw and target_kw in tgt) or (indication_kw and indication_kw in ind)
            )

            if is_target:
                target_assets.append(r)
            elif is_competitor:
                competitors.append(r)

        # Sort competitors by phase (late-stage first), cap at 20
        competitors.sort(key=lambda r: _phase_rank(r.get("临床阶段")), reverse=True)
        return target_assets[:10], competitors[:20]

    def _query_deals(self, ctx: ReportContext, inp: CommercialAssessmentInput) -> list[dict]:
        kws = [w for w in [inp.asset_name, inp.target, inp.indication] if w]
        if not kws:
            return []

        # Build OR conditions for each keyword across target + indication columns
        conds = []
        params = []
        for kw in kws:
            conds.append(
                f'("靶点" LIKE ? {LIKE_ESCAPE} OR "适应症" LIKE ? {LIKE_ESCAPE} OR "资产名称" LIKE ? {LIKE_ESCAPE})'
            )
            params.extend([like_contains(kw)] * 3)

        where = " OR ".join(conds)
        sql = (
            'SELECT "交易名称", "交易类型", "买方公司", "卖方/合作方", "资产名称", '
            '"靶点", "临床阶段", "首付款($M)", "交易总额($M)", "宣布日期" '
            f'FROM "交易" WHERE {where} '
            'ORDER BY "宣布日期" DESC LIMIT 15'
        )
        return ctx.crm_query(sql, tuple(params))

    # ── web search ──────────────────────────────────────────
    def _run_web_searches(self, inp: CommercialAssessmentInput, display: str) -> list[dict]:
        indication = inp.indication or inp.asset_name
        queries = [
            f"{indication} epidemiology prevalence incidence worldwide 2024 2025",
            f"{indication} market size TAM forecast 2025 2030 billion",
            f"{inp.asset_name} peak sales forecast analyst estimate 2025",
            f"{indication} US list price WAC annual cost reimbursement",
            f"{indication} China NMPA approval medical insurance pricing",
            f"{indication} licensing deal partnership 2024 2025 upfront milestone",
        ]
        try:
            return search_and_deduplicate(queries, max_results_per_query=3)
        except Exception:
            return []

    # ── formatting ──────────────────────────────────────────
    def _format_assets(self, assets: list[dict]) -> str:
        if not assets:
            return "(无匹配 CRM 数据)"
        lines = []
        for a in assets:
            name = a.get("资产名称") or "(unnamed)"
            company = a.get("所属客户") or "-"
            tgt = a.get("靶点") or "-"
            moa = a.get("作用机制(MOA)") or "-"
            stage = a.get("临床阶段") or "-"
            ind = a.get("适应症") or "-"
            diff = a.get("差异化分级") or ""
            peak = a.get("峰值销售预测") or ""
            peak_str = f" | 峰值预测: {peak}" if peak else ""
            lines.append(
                f"- **{name}** ({company}) | {tgt} | {moa} | {stage} | {ind}{peak_str} {diff}"
            )
        return "\n".join(lines)

    def _format_deals(self, deals: list[dict]) -> str:
        if not deals:
            return "(无可比交易数据)"
        lines = []
        for d in deals:
            date = d.get("宣布日期") or "?"
            name = d.get("交易名称") or "?"
            dtype = d.get("交易类型") or "?"
            buyer = d.get("买方公司") or "?"
            seller = d.get("卖方/合作方") or "?"
            asset = d.get("资产名称") or "-"
            tgt = d.get("靶点") or "-"
            stage = d.get("临床阶段") or "-"
            upfront = d.get("首付款($M)") or "-"
            total = d.get("交易总额($M)") or "-"
            lines.append(
                f"- [{date}] {name} | {dtype} | Buyer: {buyer} ← Seller: {seller} | "
                f"Asset: {asset} ({tgt}, {stage}) | Upfront: ${upfront}M | Total: ${total}M"
            )
        return "\n".join(lines)
