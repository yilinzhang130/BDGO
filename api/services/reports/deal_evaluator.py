"""Deal Evaluator — investment-bank four-quadrant pressure test of a biotech asset.

Given an asset's target / MoA / stage / modality / indication + any known
clinical / IP / competitive data, runs the Stage A/B/C/Path-R rubric and
produces a trade-ability assessment (.md + .docx) covering archetype,
weighted four-quadrant scores, deal thesis, risks, false-narrative flags,
buyer mapping, and transaction recommendation.
"""

from __future__ import annotations

import datetime
import logging

from pydantic import BaseModel

from services.crm.crm_lookup import asset_crm_block
from services.document import docx_builder
from services.enums import MODALITY_VALUES, PHASE_VALUES_WITH_PATH_R
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import format_web_results, safe_slug, search_and_deduplicate

logger = logging.getLogger(__name__)


class DealEvaluatorInput(BaseModel):
    company_name: str
    asset_name: str
    target: str
    moa: str | None = None
    modality: str = "small_molecule"
    indication: str
    phase: str = (
        "Phase 2"  # Preclinical | Phase 1 | Phase 2 | Phase 3 | NDA/BLA | Approved | Path R
    )
    brief: str | None = None  # Freeform data: clinical readouts, IP, competitor signals, BP claims
    include_web_search: bool = True


SYSTEM_PROMPT = """你是 BD Go 平台的资深医药投行审视官。任务：对给定 biotech 管线资产做一次 **交易吸引力压力测试**，产出结构化评估报告（markdown）。

核心视角不是"这药能不能 work"，而是 **"这资产能不能促成一笔好交易"**。

## 硬规则

1. **阶段判定**：根据资产当前阶段决定评估模式（Stage A / B / C / Path R），权重分配如下：

| 象限 | Stage A (Pre→P1) | Stage B (P1→P2) | Stage C (P2b→P3+) | Path R (改良型) |
|---|:-:|:-:|:-:|:-:|
| Q1 生物学与靶点 | 40% | 20% | 10% | 15% |
| Q2 药物形式与分子 | 25% | 20% | 15% | 25% |
| Q3 临床与监管 | 15% | 35% | 25% | 25% |
| Q4 商业交易性 | 20% | 25% | 50% | 35% |

2. **打分格式**：`[X分] (Stage X / Tier N — 简述来源)`。Tier 1 = 可独立验证（ClinicalTrials.gov / publication / FDA）；Tier 2 = BP 自述但合理（上限 4）；Tier 3 = 无实质证据（上限 3）。

3. **冷门赛道 Q4 hard cap**：过去 24 个月同赛道无 upfront ≥ $50M 交易 → Q4 ≤ 3 分，无视 TAM / 竞品数量。

4. **BIC 声称验证**：若项目方声称 "Best-in-Class" 但无定量数据（PK≥30%、safety≥50%、efficacy≥30%、convenience 整类跨越）→ Q1/Q4 均 cap 3，标红旗"伪差异化"。

5. **加权总分**：`(Q1×W1 + Q2×W2 + Q3×W3 + Q4×W4) × 4`，四舍五入到整数 / 20。

6. **中文为主，专业术语保留英文**（PK/PD、SoC、MoA、NCE、IND、PoC、NPV 等）。

7. **客观冷静**：既不是啦啦队也不唱衰。信息不足直接说"⚠️ 信息缺口"并列出需要补搜方向。

## 输出结构（严格遵循）

```markdown
# {公司} — {资产名} 交易吸引力评估

> **生成日期**: YYYY-MM-DD | **分析师**: BD Go (审视官)

## Evaluation Stage / 评估阶段
**Stage [A/B/C/Path R]** — 核心命题：[科学风险 / 临床转化风险 / 商业化风险 / 商业可行性风险]
**权重分配**: Q1(X%) Q2(X%) Q3(X%) Q4(X%)

## Asset Archetype / 资产原型
[动态命名 + 1-2 句概括，如"拥挤赛道中的差异化选手"、"早期先驱者，时机未到"]

## Four-Quadrant Assessment / 四象限评估

### Q1: Biology & Target / 生物学与靶点 — [X/5] × [W]%
**Score**: [X分] (Stage X / Tier N)
[3-4 句分析，引用具体证据]

### Q2: Modality & Molecule / 药物形式与分子 — [X/5] × [W]%
[同上]

### Q3: Clinical & Regulatory / 临床与监管 — [X/5] × [W]%
[同上]

### Q4: Commercial Transactability / 商业交易性 — [X/5] × [W]%
[同上]

## Weighted Score / 加权总分
(Q1×W1 + Q2×W2 + Q3×W3 + Q4×W4) × 4 = **XX/20**

## Innovation Level / 创新层级
Level [1.0 Me-Too | 2.0 Optimizer | 3.0 Pioneer] — [一句话理由]

## Deal Thesis / 交易逻辑
[为什么买方应该关注这资产？核心叙事是什么？2-3 段]

## Key Risks / 核心风险
1. [买方 DD 最可能卡在哪]
2. …
3. …

## False Narrative Flags / 虚假叙事警告
[BP 中站不住脚的声称；无则写"未识别"]

## Buyer Mapping / 潜在买方匹配
| 买方 | 战略适配理由 | 匹配度 |
|---|---|---|
| [MNC 名] | [pipeline gap / 战略 fit] | [High/Medium/Low] |

## Transaction Recommendation / 交易建议
- **Deal Readiness**: Dealable / Conditionally Dealable / Not Yet Dealable
- **Optimal Structure**: Acquisition / License / Newco / Option
- **Optimal Timing Window**: [何时交易窗口最好]
- **Pre-Deal Milestones**: [交易前需达成的里程碑]

## Comparable Transactions / 可比交易
[2-3 个同靶点 / 同适应症 / 同阶段历史交易，作为估值锚点；若冷门赛道则标"无直接可比"]

## Information Gaps / 信息缺口
[列出评估中信息不足的点，建议追问项目方或补搜的方向]
```
"""


USER_PROMPT = """## 资产信息
- 公司：{company}
- 资产：{asset}
- 靶点：{target}
- MoA：{moa}
- 分子形式：{modality}
- 适应症：{indication}
- 当前阶段：{phase}
- 补充信息（临床数据 / IP / 竞品 / BP 声称 等）：
{brief}

## 今天日期
{today}

## CRM 数据
{crm_block}

## 网络检索（竞品 / 可比交易 / 赛道 BD 热度）
{web_block}

**任务**：按系统提示的输出结构生成完整评估 markdown。直接以 `# {company} — {asset} 交易吸引力评估` 开头。
"""


class DealEvaluatorService(ReportService):
    slug = "deal-evaluator"
    display_name = "Deal Asset Evaluator"
    description = (
        "投行四象限交易吸引力压力测试：Stage A/B/C/Path-R 权重打分、"
        "资产原型、买方匹配、交易结构建议，输出 docx 评估报告。"
    )
    chat_tool_name = "generate_deal_evaluation"
    chat_tool_description = (
        "Run an investment-bank four-quadrant trade-ability pressure test on a biotech asset. "
        "Produces a stage-gated (Stage A/B/C/Path-R) scored evaluation with archetype, "
        "weighted score, deal thesis, buyer mapping, and transaction recommendation. "
        "Returns .md + .docx. ~120-180s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "asset_name": {"type": "string"},
            "target": {"type": "string", "description": "靶点，如 'KRAS G12C', 'Claudin 18.2'."},
            "moa": {"type": "string", "description": "作用机制（optional）。"},
            "modality": {"type": "string", "enum": MODALITY_VALUES},
            "indication": {"type": "string"},
            "phase": {"type": "string", "enum": PHASE_VALUES_WITH_PATH_R},
            "brief": {
                "type": "string",
                "description": "补充信息：临床读出、IP 状况、竞品态势、BP 核心声称。给越多越准。",
            },
            "include_web_search": {"type": "boolean", "default": True},
        },
        "required": ["company_name", "asset_name", "target", "indication", "phase"],
    }
    input_model = DealEvaluatorInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 150
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DealEvaluatorInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(f"Looking up {inp.company_name} / {inp.asset_name} in CRM…")
        crm_block = asset_crm_block(inp.company_name, inp.asset_name, include_clinical=True)

        web_block = "(网络检索未启用)"
        if inp.include_web_search:
            ctx.log("Searching web for comparable deals + competitor landscape…")
            queries = [
                f"{inp.target} {inp.indication} competitive landscape clinical stage 2025 2026",
                f"{inp.target} OR {inp.moa or inp.target} license acquisition upfront deal 2024 2025",
                f"{inp.asset_name} clinical data efficacy safety Phase",
            ]
            web = search_and_deduplicate(queries, max_results_per_query=3)
            web_block = format_web_results(web, True)
            ctx.log(f"Web search returned {len(web)} results")

        ctx.log("Running four-quadrant pressure test via LLM…")
        user_prompt = USER_PROMPT.format(
            company=inp.company_name,
            asset=inp.asset_name,
            target=inp.target,
            moa=inp.moa or "(未指定)",
            modality=inp.modality,
            indication=inp.indication,
            phase=inp.phase,
            brief=inp.brief or "(无补充)",
            today=today,
            crm_block=crm_block,
            web_block=web_block,
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=5500,
        )
        if not markdown or len(markdown) < 500:
            raise RuntimeError("LLM produced an empty or very short evaluation.")

        slug = safe_slug(f"{inp.company_name}_{inp.asset_name}")
        md_filename = f"deal_eval_{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown saved")

        ctx.log("Rendering Word document…")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{inp.company_name} — {inp.asset_name}",
            subtitle="Deal Asset Evaluation (Four-Quadrant Pressure Test)",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"deal_eval_{slug}.docx", docx_bytes, format="docx")
        ctx.log("Word document saved")

        ts_command = (
            f'/legal contract_type=ts party_position="乙方"'
            f' counterparty="{inp.company_name}"'
            f' project_name="{inp.asset_name} ({inp.indication})"'
        )

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.company_name} — {inp.asset_name} Deal Evaluation",
                "company": inp.company_name,
                "asset": inp.asset_name,
                "target": inp.target,
                "indication": inp.indication,
                "phase": inp.phase,
                "modality": inp.modality,
                "total_chars": len(markdown),
                "suggested_commands": [
                    {
                        "label": "Draft Term Sheet",
                        "command": ts_command,
                        "slug": "legal-review",
                    }
                ],
            },
        )
