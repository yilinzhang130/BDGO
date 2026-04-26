# MIRROR OF: ~/.openclaw/skills/deal-teaser-generator/SKILL.md (synced 2026-04-15)
# Sync prompts FROM SKILL.md, not the other way. See docs/SKILL_MIRROR.md.

"""Deal Teaser — 8-slide BD teaser PPT + 1-2 page Executive Summary Word doc.

Pipeline:
  1. Resolve asset in CRM (pull 差异化描述 / 峰值销售预测 / 竞品情况)
  2. Optional Tavily web search for clinical-readout + competitor quotes
  3. Single LLM call → structured JSON (deck content)
  4. Render pptx via pptx_builder + docx via docx_builder
"""

from __future__ import annotations

import datetime
import logging

from pydantic import BaseModel

from services.crm.crm_lookup import asset_crm_block
from services.document import docx_builder, pptx_builder
from services.enums import PHASE_VALUES
from services.external.llm import _extract_json_object
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import format_web_results, safe_slug, search_and_deduplicate

logger = logging.getLogger(__name__)


class DealTeaserInput(BaseModel):
    company_name: str
    asset_name: str
    indication: str
    target: str
    moa: str | None = None
    phase: str = "Phase 2"
    brief: str | None = None  # Any extra context (clinical readouts, IP, competitor list)
    include_web_search: bool = True


SYSTEM_PROMPT = """你是 BD 团队的推介材料设计师。任务：把资产分析结果浓缩成 **1 份 JSON**，供 PPT/Word 生成器使用。

## 硬规则

1. **只输出 JSON**，不要任何说明文字、不要 markdown 代码块。
2. **买方视角**：每条内容回答"为什么买方应该关注"，不是"卖方介绍自己"。
3. **数据 > 形容词**：禁止"显著改善"、"广阔市场"这种空话。每条 highlight 必须含具体数据或具体比较。
4. **中英双语**：主体中文，专业术语/金额保留英文（如 "$8.5B TAM"、"ORR 42%"）。
5. **无数据时说"⚠️ 待补充"**，不要编造。

## 输出 JSON Schema

```json
{
  "highlights": ["...", "..."],          // 3-5 条核心卖点；每条一句话 + 一个数据
  "unmet_need": "...",                    // 3-4 句话说清楚未满足需求
  "tam": "$X.XB global",                  // 市场规模 one-liner
  "peak_revenue": "$X.X-X.XB",            // Peak sales 预测区间
  "mechanism": "...",                     // 3-4 句：MoA + vs SoC 差异化
  "clinical_data": [                      // 第一行 headers，之后每行数据
    ["Metric", "Our Asset", "SoC", "Δ"],
    ["ORR", "42%", "18%", "+24 pp"]
  ],
  "competitive": [
    ["Competitor", "Company", "Stage", "Differentiation"],
    ["...", "...", "...", "..."]
  ],
  "development_plan": ["Q2 2026: Phase 1b readout", "..."],
  "deal_structure": "...",                // 一段话：期望 deal 结构 / 首付款 / 里程碑
  "contact": "..."                         // 联系方式 + Next Steps
}
```

**写作原则**：

- `highlights`：每条 ≤ 30 字，必须有数字（临床数据/TAM/专利年/差异化倍数）。
- `competitive` 至少列 3 个竞品，匿名 "同类竞品" 不可。
- `clinical_data` 无 head-to-head 可改成 "Our Asset | 来源 | 评述" 三列格式。
- `deal_structure` 给出想要的交易形式（license/option/co-dev/M&A）+ 估值锚点（引用类似交易）。
"""


USER_PROMPT = """## 资产
- 公司：{company}
- 资产：{asset}
- 靶点：{target}  ·  MoA：{moa}
- 适应症：{indication}
- 阶段：{phase}
- 补充：{brief}

## 今天日期
{today}

## CRM 数据
{crm_block}

## 网络检索（临床读出 / 竞品 / 可比交易）
{web_block}

**任务**：按 schema 生成完整 JSON。只输出 JSON。
"""


class DealTeaserService(ReportService):
    slug = "deal-teaser"
    display_name = "Deal Teaser (PPT + Word)"
    description = (
        "1-page BD 推介材料：8-slide PPT + 1-2 页 Word executive summary，"
        "买方视角叙事，数据驱动卖点、竞品对比表、deal 结构建议。"
    )
    chat_tool_name = "generate_deal_teaser"
    chat_tool_description = (
        "Generate a BD deal teaser for a biotech asset: 8-slide confidential PPT deck + "
        "1-2 page Word executive summary, written from the buyer's perspective, with "
        "data-driven highlights, competitive comparison, and proposed deal structure. "
        "Returns .pptx + .docx + .md. ~90-150s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "asset_name": {"type": "string"},
            "indication": {"type": "string"},
            "target": {"type": "string"},
            "moa": {"type": "string"},
            "phase": {"type": "string", "enum": PHASE_VALUES},
            "brief": {
                "type": "string",
                "description": "补充信息（临床读出 / IP / 竞品 / 可比交易）。可选。",
            },
            "include_web_search": {"type": "boolean", "default": True},
        },
        "required": ["company_name", "asset_name", "indication", "target", "phase"],
    }
    input_model = DealTeaserInput
    mode = "async"
    output_formats = ["pptx", "docx", "md"]
    estimated_seconds = 120
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DealTeaserInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(f"Looking up {inp.asset_name} in CRM…")
        crm_block = asset_crm_block(inp.company_name, inp.asset_name)

        web_block = "(网络检索未启用)"
        if inp.include_web_search:
            ctx.log("Searching web for clinical readouts + competitors + comps…")
            queries = [
                f"{inp.asset_name} clinical data efficacy safety Phase readout 2025",
                f"{inp.target} {inp.indication} competitive landscape standard of care",
                f"{inp.target} {inp.indication} license deal upfront milestone 2024 2025",
            ]
            web = search_and_deduplicate(queries, max_results_per_query=3)
            web_block = format_web_results(web, True)
            ctx.log(f"Web search returned {len(web)} results")

        ctx.log("LLM: composing buyer-facing teaser content…")
        user_prompt = USER_PROMPT.format(
            company=inp.company_name,
            asset=inp.asset_name,
            target=inp.target,
            moa=inp.moa or "(未指定)",
            indication=inp.indication,
            phase=inp.phase,
            brief=inp.brief or "(无)",
            today=today,
            crm_block=crm_block,
            web_block=web_block,
        )
        raw = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=3500,
        )
        data = _extract_json_object(raw)
        if not data:
            raise RuntimeError(
                "LLM did not return parseable JSON teaser content. Raw head: " + (raw or "")[:400]
            )

        highlights = [str(x) for x in (data.get("highlights") or [])][:5] or ["⚠️ 待补充 highlights"]
        development_plan = [str(x) for x in (data.get("development_plan") or [])][:6] or [
            "⚠️ 待补充里程碑"
        ]
        content = pptx_builder.TeaserContent(
            asset_name=inp.asset_name,
            indication=inp.indication,
            company=inp.company_name,
            target=inp.target,
            moa=inp.moa or (data.get("mechanism", "")[:80] or "(未指定)"),
            phase=inp.phase,
            date=today,
            highlights=highlights,
            unmet_need=str(data.get("unmet_need") or "⚠️ 待补充"),
            tam=str(data.get("tam") or "⚠️ 待补充"),
            peak_revenue=str(data.get("peak_revenue") or "⚠️ 待补充"),
            mechanism=str(data.get("mechanism") or "⚠️ 待补充"),
            clinical_data=_coerce_table(data.get("clinical_data")),
            competitive=_coerce_table(data.get("competitive")),
            development_plan=development_plan,
            deal_structure=str(data.get("deal_structure") or "⚠️ 待补充"),
            contact=str(data.get("contact") or "Contact: BD Go team · bdgo@[company].com"),
        )

        slug = safe_slug(f"{inp.company_name}_{inp.asset_name}")
        ctx.log("Rendering PPT deck…")
        pptx_bytes = pptx_builder.build_deck(content)
        pptx_filename = f"deal_teaser_{slug}.pptx"
        ctx.save_file(pptx_filename, pptx_bytes, format="pptx")

        markdown = _build_exec_summary_md(inp, content, today)
        md_filename = f"deal_teaser_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")

        ctx.log("Rendering Word executive summary…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{inp.asset_name}",
            subtitle=f"Deal Teaser — Executive Summary · {inp.indication}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"deal_teaser_{slug}.docx", docx_bytes, format="docx")

        # BD lifecycle stage 3: after teaser, the natural next move is an NDA.
        # Pre-build the /legal slash command so the chat UI can offer it as a chip.
        nda_command = (
            f'/legal contract_type=cda party_position="乙方"'
            f' counterparty="{inp.company_name}"'
            f' project_name="{inp.asset_name} ({inp.indication})"'
        )

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.company_name} — {inp.asset_name} Deal Teaser",
                "company": inp.company_name,
                "asset": inp.asset_name,
                "indication": inp.indication,
                "target": inp.target,
                "phase": inp.phase,
                "highlights_count": len(highlights),
                "suggested_commands": [
                    {
                        "label": "Draft NDA / CDA",
                        "command": nda_command,
                        "slug": "legal-review",
                    }
                ],
            },
        )


def _coerce_table(raw) -> list[list[str]]:
    """LLM may hand us strings instead of 2D arrays — normalize defensively."""
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    out = []
    for row in raw:
        if isinstance(row, list):
            out.append([str(c) if c is not None else "" for c in row])
        elif isinstance(row, dict):
            out.append([str(v) if v is not None else "" for v in row.values()])
        else:
            out.append([str(row)])
    return out


def _build_exec_summary_md(inp: DealTeaserInput, c: pptx_builder.TeaserContent, today: str) -> str:
    highlights_md = "\n".join(f"- {h}" for h in c.highlights)
    milestones_md = "\n".join(f"- {m}" for m in c.development_plan)

    def _table_md(t: list[list[str]]) -> str:
        if not t or len(t) < 2:
            return "(no data)"
        headers = t[0]
        sep = "|" + "|".join(["---"] * len(headers)) + "|"
        body = "\n".join(
            "| " + " | ".join(r + [""] * (len(headers) - len(r))) + " |" for r in t[1:]
        )
        return "| " + " | ".join(headers) + " |\n" + sep + "\n" + body

    return f"""# {inp.asset_name} — Deal Teaser Executive Summary

> **Company**: {inp.company_name}  |  **Indication**: {inp.indication}  |  **Phase**: {inp.phase}
> **Target / MoA**: {inp.target} / {c.moa}
> **Date**: {today}  ·  **CONFIDENTIAL — For Discussion Purposes Only**

## Investment Highlights
{highlights_md}

## Asset Overview
| 属性 | 详情 |
|---|---|
| 资产名称 | {inp.asset_name} |
| 所属公司 | {inp.company_name} |
| 靶点 / MoA | {inp.target} / {c.moa} |
| 适应症 | {inp.indication} |
| 临床阶段 | {inp.phase} |
| TAM | {c.tam} |
| Peak Revenue | {c.peak_revenue} |

## Unmet Need & Market Opportunity
{c.unmet_need}

## Mechanism & Differentiation
{c.mechanism}

## Clinical Data Snapshot
{_table_md(c.clinical_data)}

## Competitive Landscape
{_table_md(c.competitive)}

## Development Plan & Catalysts
{milestones_md}

## Proposed Deal Structure
{c.deal_structure}

## Next Steps / Contact
{c.contact}

---
*CONFIDENTIAL — For Discussion Purposes Only · Prepared by BD Go · {today}*
"""
