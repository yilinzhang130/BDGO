# MIRROR OF: ~/.openclaw/skills/rnpv-valuation/SKILL.md (synced 2026-04-24)
# Sync prompts FROM SKILL.md, not the other way. See docs/SKILL_MIRROR.md.

"""rNPV Valuation — DCF-style Excel model for biotech pipeline assets.

Pipeline:
  1. Resolve company / asset in CRM to seed metadata (modality, phase, TA)
  2. Optional Tavily web search for pricing comps + epidemiology anchors
  3. Single-shot LLM call producing a structured JSON config
  4. Generate .xlsx via services.document.rnpv_excel.generate()
  5. Also produce a short markdown summary of key outputs (rNPV, peak rev)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

from services.crm.crm_lookup import asset_crm_block
from services.document import rnpv_excel
from services.enums import MODALITY_VALUES, PHASE_VALUES
from services.external.llm import _extract_json_object
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import format_web_results, safe_slug, search_and_deduplicate

logger = logging.getLogger(__name__)


_BENCHMARKS_PATH = (
    Path(__file__).resolve().parent.parent / "document" / "rnpv_default_benchmarks.json"
)
_BENCHMARKS_STR: str | None = None


def _load_benchmarks() -> str:
    """Return the default benchmarks JSON as a string for prompt injection."""
    global _BENCHMARKS_STR
    if _BENCHMARKS_STR is None:
        try:
            _BENCHMARKS_STR = _BENCHMARKS_PATH.read_text(encoding="utf-8")
        except OSError:
            logger.warning("rnpv default benchmarks not found at %s", _BENCHMARKS_PATH)
            _BENCHMARKS_STR = "{}"
    return _BENCHMARKS_STR


class RNPVInput(BaseModel):
    company_name: str
    asset_name: str
    indication: str
    phase: str = "Phase 2"
    modality: str = "small_molecule"
    therapeutic_area: str = "Oncology"
    target: str | None = None
    moa: str | None = None
    brief: str | None = None  # Free-form context to seed assumptions
    include_web_search: bool = True


SYSTEM_PROMPT = """你是 BD Go 平台的资深医药投行估值分析师。任务：为给定资产输出一份 **严格合法的 JSON config**，供 Excel rNPV 生成器使用。

硬规则：
1. **只输出 JSON**，不要有任何说明文字、不要 markdown 代码块。
2. 所有字段类型必须严格正确：数字用数字、比率用 0-1 小数、字符串用字符串。
3. 每个关键参数必须在 `data_sources` 中标注来源；无法验证的估计值标注 "⚠️ benchmark" 或 "⚠️ estimate"。
4. R&D 按阶段拆分，每 phase 含 num_trials / patients_per_trial / num_sites / cost_per_patient_k。
5. SG&A 必须拆分为 sales_team / msls / marketing / ga_pct_of_revenue。
6. PoS 使用 phase-specific 基准；资产 specific 调整请标注原因在 data_sources。
7. `projection_years` 默认 20，`base_year` 用今天的年份。
8. 至少一个 `indications` 条目；如适应症多条，逐条独立建模。
9. **references 数组必填**：每条 data_source 尽量对应一个 reference；用 `⚠️ benchmark` 标记的来源分配到 "Industry Benchmarks" category。
"""

USER_PROMPT = """## 资产信息
- 公司：{company}
- 资产：{asset}
- 适应症：{indication}
- 临床阶段：{phase}
- 分子形式：{modality}
- 治疗领域：{ta}
- 靶点/MoA：{target} / {moa}
- 补充说明：{brief}

## 今天日期
{today}

## 已知参考数据（CRM）
{crm_block}

## 网络检索结果（定价 / 流行病学 / 竞品）
{web_block}

## 行业基准参考
{benchmarks}

## 任务
生成完整 JSON config（schema 见下），使用 CRM + 网络检索数据填充，缺失项用行业基准（必须标 ⚠️）。
**只输出 JSON，不要任何其他文字。**

```json
{{
  "metadata": {{
    "company": "...",
    "asset": "...",
    "modality": "small_molecule|biologic_antibody|adc|cell_gene_therapy|nucleic_acid_rna",
    "therapeutic_area": "...",
    "analyst": "BD Go",
    "date": "YYYY-MM-DD",
    "base_year": 2026,
    "shares_outstanding_mm": 100
  }},
  "indications": [
    {{
      "name": "...",
      "line_of_therapy": "1L|2L|3L+",
      "years_to_launch": 5,
      "geography_data": {{
        "US": {{"population": 330000000, "prevalence": 150000, "diagnosed_rate": 0.65, "eligible_rate": 0.80, "line_share": 0.35, "drug_treatable_rate": 0.90, "addressable_rate": 0.70}},
        "EU5": {{...}},
        "China": {{...}},
        "Japan": {{...}}
      }},
      "pricing": {{"US": 150000, "EU5": 90000, "China": 30000, "Japan": 120000}},
      "gross_to_net": {{"US": 0.55, "EU5": 0.75, "China": 0.65, "Japan": 0.80}},
      "penetration_curve": {{"peak": 0.15, "ramp_years": 7, "loe_year_from_launch": 12, "post_loe_erosion_per_year": 0.30}},
      "pos": {{
        "current_phase": "Phase 2",
        "phase_transitions": {{"phase2_to_phase3": 0.35, "phase3_to_nda": 0.58, "nda_to_approval": 0.90}},
        "cumulative": 0.183
      }},
      "data_sources": {{"prevalence": "SEER 2024 [R1]", "pricing": "Competitor X $145K [R2]", "diagnosed_rate": "⚠️ benchmark"}}
    }}
  ],
  "costs": {{
    "rd_by_phase": [
      {{"phase": "Phase 2", "cost_mm": 40, "duration_years": 2.5, "start_year": 0, "num_trials": 1, "patients_per_trial": 250, "num_sites": 50, "cost_per_patient_k": 120, "monitoring_cost_mm": 5, "data_management_mm": 3, "source": "..."}},
      {{"phase": "Phase 3", "cost_mm": 150, "duration_years": 3, "start_year": 3, "num_trials": 2, "patients_per_trial": 400, "num_sites": 80, "cost_per_patient_k": 150, "monitoring_cost_mm": 12, "data_management_mm": 6, "source": "..."}}
    ],
    "cmc": {{"process_development_mm": 8, "manufacturing_facility_mm": 15, "clinical_supply_mm": 5}},
    "cogs_margin": 0.20,
    "sga": {{
      "sales_team": {{"reps": 120, "cost_per_rep_k": 280, "ramp_schedule": [0.3, 0.6, 1.0]}},
      "msls": {{"count": 20, "cost_per_msl_k": 350}},
      "marketing": {{"congress_annual_mm": 3, "publications_mm": 1, "digital_marketing_mm": 2, "prelaunch_total_mm": 5}},
      "ga_pct_of_revenue": 0.05
    }}
  }},
  "discount": {{"wacc": 0.13, "wacc_source": "Clinical stage late biotech benchmark", "tax_rate": 0.20, "projection_years": 20}},
  "references": [
    {{"id": "R1", "category": "Epidemiology", "description": "...", "type": "Database / Registry", "date": "2024", "url": "..."}},
    {{"id": "R2", "category": "Pricing & Reimbursement", "description": "...", "type": "Pricing Database", "date": "2024", "url": "..."}}
  ]
}}
```
"""


class RNPVValuationService(ReportService):
    slug = "rnpv-valuation"
    display_name = "rNPV Valuation Model"
    description = (
        "生成 10-sheet 公式驱动的 Excel rNPV 估值模型。"
        "从流行病学构建患者漏斗 → 收入/成本/PoS/WACC → 输出可直接用于谈判的 xlsx。"
    )
    chat_tool_name = "generate_rnpv_model"
    chat_tool_description = (
        "Generate a formula-driven 10-sheet rNPV (risk-adjusted NPV) valuation Excel for a biotech pipeline asset. "
        "Takes company + asset + indication + clinical phase; returns .xlsx with editable assumptions, "
        "patient funnel, revenue/cost build, cash flow, PoS-gated NPV, sensitivity, QC, and references sheets. "
        "~120-240s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "公司名（英文或中文），如 'Ascentage Pharma'。",
            },
            "asset_name": {
                "type": "string",
                "description": "资产/药物名或代号，如 'APG-2575' 或 'lisaftoclax'。",
            },
            "indication": {"type": "string", "description": "适应症，如 'CLL 2L+'。"},
            "phase": {"type": "string", "enum": PHASE_VALUES, "description": "当前临床阶段。"},
            "modality": {"type": "string", "enum": MODALITY_VALUES, "description": "分子形式。"},
            "therapeutic_area": {
                "type": "string",
                "description": "治疗领域（Oncology / CNS / Rare Disease 等）。",
            },
            "target": {"type": "string", "description": "靶点（optional）。"},
            "moa": {"type": "string", "description": "作用机制（optional）。"},
            "brief": {
                "type": "string",
                "description": "补充说明，如关键临床数据、差异化、竞品（optional，帮助 LLM 精化假设）。",
            },
            "include_web_search": {"type": "boolean", "default": True},
        },
        "required": ["company_name", "asset_name", "indication", "phase", "modality"],
    }
    input_model = RNPVInput
    mode = "async"
    output_formats = ["xlsx", "md"]
    estimated_seconds = 180
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = RNPVInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(f"Looking up {inp.company_name} / {inp.asset_name} in CRM…")
        crm_block = asset_crm_block(inp.company_name, inp.asset_name)

        web_block = "(网络检索未启用)"
        if inp.include_web_search:
            ctx.log("Searching web for epidemiology + pricing comps…")
            queries = [
                f"{inp.indication} epidemiology prevalence incidence US EU China",
                f"{inp.indication} standard of care pricing list price annual cost",
                f"{inp.asset_name} OR {inp.target or inp.asset_name} clinical data Phase results",
            ]
            web = search_and_deduplicate(queries, max_results_per_query=3)
            web_block = format_web_results(web, True)
            ctx.log(f"Web search returned {len(web)} results")

        ctx.log("Calling LLM to build rNPV config JSON…")
        user_prompt = USER_PROMPT.format(
            company=inp.company_name,
            asset=inp.asset_name,
            indication=inp.indication,
            phase=inp.phase,
            modality=inp.modality,
            ta=inp.therapeutic_area,
            target=inp.target or "(未指定)",
            moa=inp.moa or "(未指定)",
            brief=inp.brief or "(无)",
            today=today,
            crm_block=crm_block,
            web_block=web_block,
            benchmarks=_load_benchmarks(),
        )
        raw = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=6000,
        )
        config = _extract_json_object(raw)
        if not config:
            raise RuntimeError(
                "LLM did not return parseable JSON config for rNPV generator. "
                "Raw head: " + (raw or "")[:400]
            )

        # Guarantee required identity fields — generator reads them for filenames & sheet headers.
        md = config.setdefault("metadata", {})
        md.setdefault("company", inp.company_name)
        md.setdefault("asset", inp.asset_name)
        md.setdefault("modality", inp.modality)
        md.setdefault("therapeutic_area", inp.therapeutic_area)
        md.setdefault("analyst", "BD Go")
        md.setdefault("date", today)
        md.setdefault("base_year", datetime.date.today().year)

        slug = safe_slug(f"{inp.company_name}_{inp.asset_name}")
        config_filename = f"rnpv_config_{slug}.json"
        ctx.save_file(
            config_filename, json.dumps(config, ensure_ascii=False, indent=2), format="json"
        )
        ctx.log(f"Config JSON saved ({config_filename})")

        ctx.log("Generating 10-sheet formula-driven Excel model…")
        xlsx_filename = f"rnpv_{slug}.xlsx"
        rnpv_excel.generate(config, os.fspath(ctx.output_dir / xlsx_filename))
        gf = ctx.register_file(xlsx_filename, format="xlsx")
        ctx.log(f"Excel saved ({xlsx_filename}, {gf.size // 1024} KB)")

        markdown = self._summary_markdown(inp, today, config, xlsx_filename)
        md_filename = f"rnpv_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")

        ts_command = (
            f'/legal contract_type=ts party_position="乙方"'
            f' counterparty="{inp.company_name}"'
            f' project_name="{inp.asset_name} ({inp.indication})"'
        )

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.company_name} — {inp.asset_name} rNPV",
                "company": inp.company_name,
                "asset": inp.asset_name,
                "indication": inp.indication,
                "phase": inp.phase,
                "modality": inp.modality,
                "rnpv_mm": config.get("_npv", 0),
                "unrisked_npv_mm": config.get("_unrisked_npv", 0),
                "peak_revenue_mm": config.get("_peak_rev", 0),
                "peak_revenue_year": config.get("_peak_rev_year", "N/A"),
                "qc": {
                    "pass": config.get("_qc_pass", 0),
                    "warn": config.get("_qc_warn", 0),
                    "fail": config.get("_qc_fail", 0),
                },
                "ref_coverage_pct": config.get("_ref_coverage_pct", 0),
                "suggested_commands": [
                    {
                        "label": "Draft Term Sheet",
                        "command": ts_command,
                        "slug": "legal-review",
                    }
                ],
            },
        )

    def _summary_markdown(
        self, inp: RNPVInput, today: str, config: dict, xlsx_filename: str
    ) -> str:
        npv = config.get("_npv", 0)
        unrisked = config.get("_unrisked_npv", 0)
        peak_rev = config.get("_peak_rev", 0)
        peak_yr = config.get("_peak_rev_year", "N/A")
        qc_pass = config.get("_qc_pass", 0)
        qc_warn = config.get("_qc_warn", 0)
        qc_fail = config.get("_qc_fail", 0)
        ref_coverage = config.get("_ref_coverage_pct", 0)

        shares = config.get("metadata", {}).get("shares_outstanding_mm", 0)
        per_share = f"${npv / shares:,.2f}" if shares else "N/A"
        qc_icon = "✅" if qc_fail == 0 else "⚠️"
        indications = config.get("indications", []) or []
        ind_rows = []
        for ind in indications:
            pos = ind.get("pos", {}).get("cumulative", 0)
            peak = ind.get("penetration_curve", {}).get("peak", 0)
            ind_rows.append(
                f"| {ind.get('name', '?')} | {ind.get('line_of_therapy', '?')} | "
                f"{ind.get('years_to_launch', '?')} | {pos:.1%} | {peak:.1%} |"
            )

        ind_table = (
            (
                "| 适应症 | 线别 | Years to Launch | Cumulative PoS | Peak Penetration |\n"
                "|---|---|---|---|---|\n" + "\n".join(ind_rows)
            )
            if ind_rows
            else "(无适应症数据)"
        )

        return f"""# {inp.company_name} — {inp.asset_name} rNPV 估值摘要

> **生成日期**: {today} | **分析师**: BD Go | **数据源**: CRM + Web + 行业基准

## 关键结果

| 指标 | 数值 |
|---|---|
| **rNPV (risk-adjusted)** | **${npv:,.1f}M** |
| Unrisked NPV | ${unrisked:,.1f}M |
| Peak Revenue | ${peak_rev:,.1f}M (@ {peak_yr}) |
| Per-Share Value | {per_share} |
| WACC | {config.get("discount", {}).get("wacc", 0):.1%} |
| 投影年限 | {config.get("discount", {}).get("projection_years", 20)} yrs |

## 资产信息
- **公司** / **资产**：{inp.company_name} / {inp.asset_name}
- **适应症**：{inp.indication}
- **阶段** / **分子形式**：{inp.phase} / {inp.modality}
- **治疗领域**：{inp.therapeutic_area}

## 适应症建模
{ind_table}

## 质控 & 引用
- {qc_icon} QC: {qc_pass} pass / {qc_warn} warn / {qc_fail} fail
- 📚 参考引用覆盖率：{ref_coverage:.0%}

## 下载
- Excel 模型：`{xlsx_filename}`（10 sheets，所有假设可编辑，公式自动重算）
- JSON config：可用于后续微调和复跑

> ⚠️ 本模型为投行 DCF 估值框架，所有假设需与项目方共同确认；标注 `⚠️ benchmark` 的参数建议替换为主来源数据。
"""
