"""Buyer Matching — 反向查询：基于资产找 Top-N 买方 (S2-01).

给定资产信息（靶点/适应症/阶段/分子类型），从 MNC画像 表中扫描所有已知买方，
用 LLM 对每家 MNC 的战略契合度打分并排序，输出 Top-N 买方候选清单 + 接触策略。

Pipeline:
  1. 从 MNC画像 拉取全部 company_name + heritage_ta + bd_pattern_theses + sunk_cost_by_ta
  2. Tavily 搜索：同靶点/适应症近期 deal 报道
  3. 单次 LLM 调用：对比资产 vs 每家 MNC 战略 → 排序 + 理由
  4. 输出 .md + .docx（表格 + per-buyer 接触建议）
"""

from __future__ import annotations

import datetime
import json
import logging

from pydantic import BaseModel, Field, model_validator

from services.document import docx_builder
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


class BuyerMatchingInput(BaseModel):
    target: str = Field(..., description="靶点，如 'KRAS G12C', 'Claudin 18.2'")
    indication: str = Field(..., description="适应症，如 'NSCLC 一线', '三阴乳腺癌'")
    phase: str = Field(..., description="临床阶段，如 'Phase 2', 'Preclinical'")
    modality: str = Field(
        "small_molecule",
        description="分子类型：small_molecule / antibody / ADC / CAR-T / cell_gene / RNA / bispecific",
    )
    asset_brief: str | None = Field(
        None,
        description="补充信息：差异化声称 / 已有数据 / IP 状况 / 竞品优劣（给越多越准）",
    )
    top_n: int = Field(5, ge=3, le=10, description="返回 Top-N 买方（3-10，默认 5）")
    include_web_search: bool = True

    @model_validator(mode="after")
    def validate_inputs(self) -> BuyerMatchingInput:
        if not self.target.strip():
            raise ValueError("target cannot be empty")
        if not self.indication.strip():
            raise ValueError("indication cannot be empty")
        return self


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """你是 BD Go 平台的资深买方匹配分析师。任务：给定一个 biotech 资产，从已知 MNC 买方库中找出最有可能发起交易的 Top-N 家，并给出战略契合度评分和接触策略建议。

硬规则：
1. **战略契合度评分（1-5 分）** — 综合考虑：
   - Heritage TA 与适应症匹配度
   - 历史 BD pattern 与当前资产阶段/类型是否一致
   - 近期已有的 sunk cost（已入场的赛道更可能加仓）
   - 近期公开信号（deal announcement / pipeline gap）
2. **不编造交易** — 如果没有已知的可比交易，写"未见公开可比交易"
3. **不推荐没有数据的 MNC** — 数据不足的买方排在后面，注明 [数据有限]
4. **接触策略要 specific** — 不要泛泛说"了解合作意向"，要说"切入点：他们的 KRAS G12C 项目 Phase 2 临近读出，此时引入一个互补的 G12D 资产做搭配...""
5. **中文为主，公司名/靶点/deal 类型保留英文**
"""

_USER_PROMPT = """## 待售资产信息
- 靶点: {target}
- 适应症: {indication}
- 当前阶段: {phase}
- 分子类型: {modality}
- 补充信息: {asset_brief}

## 今天日期
{today}

## 已知 MNC 买方数据（来自 BDGO CRM MNC画像表，{n_mnc} 家）
{mnc_block}

## 网络搜索：同赛道近期 BD deal
{web_block}

## 任务
从上述 MNC 中挑选 Top {top_n} 家，给出战略契合度评分（1-5）+ 理由 + 具体接触策略。

输出格式（严格遵循）：

```markdown
# {target} {indication} — Top {top_n} 买方候选清单

> **生成日期**: {today} | **资产阶段**: {phase} | **分子类型**: {modality}

## 排名总览

| 排名 | 买方 | 战略契合度 | 核心理由 |
|------|------|-----------|----------|
| 1 | [公司] | ⭐⭐⭐⭐⭐ (5/5) | [一句话] |
| 2 | ... | ... | ... |

## 逐家分析

### #1 — [公司名]
**战略契合度**: X/5
**核心契合点**: [2-3 句，引用 CRM 数据或 web deal，标 [CRM] 或 [Web]]
**买方可能的诉求**: [他们为什么想买？pipeline gap / revenue diversification / geography?]
**接触策略**: [具体切入点 + 推荐的第一步行动]
**关键风险**: [如果有的话]

### #2 — ...

## 候补观察名单

[剩余 MNC 中有潜力但证据不足的，简要列出 2-3 家，一句话理由]

## 建议下一步
1. [行动 1]
2. [行动 2]
3. [行动 3]
```

直接输出 markdown，不要前言。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class BuyerMatchingService(ReportService):
    slug = "buyer-matching"
    display_name = "Top-N Buyer Matching"
    description = (
        "反向买方匹配：给定资产（靶点/适应症/阶段/分子类型），"
        "从 MNC画像 CRM 扫描所有已知买方，LLM 排序 Top-N 战略契合度 + 接触策略建议。"
    )
    chat_tool_name = "find_top_buyers"
    chat_tool_description = (
        "Reverse buyer matching: given a biotech asset (target/indication/phase/modality), "
        "scan all known MNCs in the CRM and rank the top-N by strategic fit. "
        "Returns a ranked shortlist with per-buyer deal thesis and outreach strategy. "
        "~60-90s. Returns .md + .docx."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "靶点，如 'KRAS G12C'"},
            "indication": {"type": "string", "description": "适应症，如 'NSCLC 一线'"},
            "phase": {
                "type": "string",
                "description": "临床阶段",
            },
            "modality": {
                "type": "string",
                "description": "分子类型",
                "default": "small_molecule",
            },
            "asset_brief": {
                "type": "string",
                "description": "补充信息：差异化声称、临床数据、IP 状况等（可选，给越多越准）",
            },
            "top_n": {
                "type": "integer",
                "description": "返回 Top-N 买方（3-10，默认 5）",
                "default": 5,
                "minimum": 3,
                "maximum": 10,
            },
            "include_web_search": {
                "type": "boolean",
                "default": True,
                "description": "搜索近期同赛道 BD deal（增加准确度）",
            },
        },
        "required": ["target", "indication", "phase"],
    }
    input_model = BuyerMatchingInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 90
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = BuyerMatchingInput(**params)
        today = datetime.date.today().isoformat()

        # Phase 1 — Load MNC candidates from CRM
        ctx.log("加载 MNC画像 候选买方...")
        mnc_rows = ctx.crm_query(
            'SELECT company_name, company_cn, heritage_ta, bd_pattern_theses, '
            'sunk_cost_by_ta, deal_size_preference, innovation_philosophy '
            'FROM "MNC画像" ORDER BY company_name LIMIT 60',
        )
        ctx.log(f"MNC画像 返回 {len(mnc_rows)} 家候选买方")

        # Phase 2 — Web search for comparable deals in same TA
        web_block = "(网络检索未启用)"
        if inp.include_web_search:
            ctx.log("Tavily 3 次搜索（同靶点/适应症近期 deal）...")
            queries = [
                f"{inp.target} {inp.indication} license acquisition deal upfront 2024 2025 2026",
                f"{inp.indication} {inp.modality} MNC BD partnership pharma 2025",
                f"{inp.target} biotech deal news announcement 2025 2026",
            ]
            web = search_and_deduplicate(queries, max_results_per_query=3)
            web_block = format_web_results(web, True)
            ctx.log(f"网络搜索返回 {len(web)} 条结果")

        # Phase 3 — Build MNC data block for LLM
        mnc_block = self._format_mnc_block(mnc_rows)

        # Phase 4 — LLM ranking
        ctx.log(f"LLM 匹配打分 Top-{inp.top_n}...")
        user_prompt = _USER_PROMPT.format(
            target=inp.target,
            indication=inp.indication,
            phase=inp.phase,
            modality=inp.modality,
            asset_brief=inp.asset_brief or "(无补充)",
            today=today,
            n_mnc=len(mnc_rows),
            mnc_block=mnc_block,
            web_block=web_block,
            top_n=inp.top_n,
        )
        markdown = ctx.llm(
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4000,
        )
        if not markdown or len(markdown) < 300:
            raise RuntimeError("Buyer matching LLM returned empty output.")

        # Phase 5 — Save outputs
        slug = safe_slug(f"{inp.target}_{inp.indication}") or "asset"
        md_name = f"buyer_match_{slug}_{today}.md"
        docx_name = f"buyer_match_{slug}_{today}.docx"

        ctx.save_file(md_name, markdown, format="md")
        ctx.log("Markdown 已保存")

        ctx.log("渲染 Word 文档...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{inp.target} {inp.indication} — Top-{inp.top_n} 买方候选清单",
            subtitle=f"{inp.phase} · {inp.modality} · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(docx_name, docx_bytes, format="docx")
        ctx.log("Word 已保存")

        # Chips: encourage following up with /mnc deep-dive on top candidates
        suggested_commands = [
            {
                "label": "MNC Deep-dive",
                "command": f'/mnc company_name="[买方名]" focus_ta="{inp.indication}"',
                "slug": "buyer-profile",
            },
            {
                "label": "Outreach Email",
                "command": (
                    f'/email target="{inp.target}" indication="{inp.indication}"'
                    f' phase="{inp.phase}"'
                ),
                "slug": "outreach-email",
            },
        ]

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.target} {inp.indication} Top-{inp.top_n} Buyer Matching",
                "target": inp.target,
                "indication": inp.indication,
                "phase": inp.phase,
                "modality": inp.modality,
                "top_n": inp.top_n,
                "n_mnc_candidates": len(mnc_rows),
                "suggested_commands": suggested_commands,
            },
        )

    # ── helpers ─────────────────────────────────────────────

    def _format_mnc_block(self, rows: list[dict]) -> str:
        """Format MNC candidates as a compact block for the LLM."""
        if not rows:
            return "(MNC画像 表为空 — 将基于通用行业知识推断)"

        parts: list[str] = []
        for row in rows:
            name = row.get("company_name") or row.get("company_cn") or "?"
            lines = [f"**{name}**"]
            if row.get("heritage_ta"):
                lines.append(f"  Heritage TA: {row['heritage_ta']}")
            if row.get("bd_pattern_theses"):
                raw = row["bd_pattern_theses"]
                # May be JSON string or already parsed
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                        raw = (
                            "; ".join(parsed) if isinstance(parsed, list) else str(parsed)[:200]
                        )
                    except (json.JSONDecodeError, TypeError):
                        pass
                lines.append(f"  BD patterns: {str(raw)[:200]}")
            if row.get("sunk_cost_by_ta"):
                raw = row["sunk_cost_by_ta"]
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        pass
                lines.append(f"  Sunk cost TAs: {str(raw)[:200]}")
            if row.get("deal_size_preference"):
                lines.append(f"  Deal size: {row['deal_size_preference']}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)
