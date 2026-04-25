"""
Company Analysis — bidirectional company snapshot for BD workflows.

Given a company name, produces a structured analysis from one of three
perspectives:

  - buyer    我方是 MNC/PE，看 biotech (potential seller / target)
  - seller   我方是 biotech，看 MNC (potential buyer / partner)
  - neutral  comprehensive snapshot, no recommendation

Pipeline:
  1. CRM lookup — company row + all assets + deals where this company is
     buyer or seller
  2. Optional Tavily web search (4 queries: BD activity, pipeline,
     leadership, financials)
  3. Single LLM call → structured markdown
  4. Render .md + .docx
  5. Suggest a next-step chip (most common: /email cold_outreach)

Sister service to /mnc (buyer-profile, MNC-buyer-specific). /company is
the generic bidirectional version usable for any company on either side
of a deal.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from crm_store import LIKE_ESCAPE, like_contains
from pydantic import BaseModel, Field

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


class CompanyAnalysisInput(BaseModel):
    company_name: str = Field(..., description="Company to analyze (CRM 公司名 or free text)")
    perspective: Literal["buyer", "seller", "neutral"] = "neutral"
    focus: str | None = Field(
        None,
        description=(
            "Free-text focus, e.g. '重点看 BD 历史和管线 gap' or 'evaluate fit for our KRAS asset'."
        ),
    )
    include_web_search: bool = True


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 的资深公司分析师。任务：给定一家公司，从特定 BD 视角输出一份**结构化、证据驱动**的公司分析报告。

## 硬规则

1. **输出 markdown**，无 JSON、无代码块包裹整体内容（表格除外）。
2. **每条结论必须有依据**：CRM 数据、网络检索条目、或显式标注「⚠️ 待补充」。禁止凭空编造交易额、团队名字、临床数据。
3. **数据 > 形容词**：禁用「行业领先」、「巨大潜力」、「前景广阔」。每个论断必须配数字 / 时间 / 具体事件。
4. **中英双语**：主体中文，金额/术语保留英文（"$1.2B upfront"、"Phase 2 ORR 38%"、"FY2024 cash runway 18 months"）。
5. **视角驱动**：根据 perspective 字段调整框架（见下文），但分析数据本身一致。
6. **不替代法律 / 投资意见**：不做"买入 / 卖出"建议，只做信息整合 + BD 决策辅助。

## 视角差异（同样数据，不同 takeaway）

- **buyer**（我方是 MNC / PE，看 biotech 候选）
  - 核心问题：这家 biotech 的资产值不值得 license-in？团队/财务能撑到关键 readout 吗？IP 干净吗？
  - 章节侧重：管线深度、临床里程碑、cash runway、IP/FTO、可能的 deal 结构
  - 建议下一步：联系 / DD / 估值

- **seller**（我方是 biotech，看 MNC / 大药厂买方）
  - 核心问题：这家 MNC 在买什么？我们的资产 fits 吗？谁是 BD 决策人？最近有什么类似交易？
  - 章节侧重：BD 历史（近 24 月交易、合作模式）、TA 偏好、leadership / BD team、决策周期
  - 建议下一步：cold outreach 切入点 / pitch 角度

- **neutral**（综合 snapshot，无推荐）
  - 章节平均覆盖，不做行动建议
  - 用于团队内部 brief / 给 partner 的背景资料

## 输出结构（严格按此 8 节）

```
# {公司名} 公司分析 ({perspective_label})

> **生成日期**: {today}  ·  **分析视角**: {perspective_label}  ·  **CRM 命中**: ✓/✗

## 一、一页摘要
（3-5 句话，≤ 200 字，回答：这家公司是谁 / 阶段 / 当前 BD 处境 / 视角化的 takeaway）

## 二、公司基本面
- 成立时间 / 总部 / 上市状态 / 市值或最近估值
- 雇员规模 / cash runway（如 public 可查或 web 检索）
- 主营业务 / TA 重点

## 三、管线 / 核心资产
- 表格列出 CRM 中的资产（资产名 | 靶点 | 阶段 | 适应症 | 差异化分级）
- 如果 CRM 无数据，使用 web search 补充并明确标注来源
- ≤ 6 条；多于 6 条择 BD 优先级最高的列出

## 四、BD 历史
- 近 24 个月相关交易（in/out-license, M&A, partnership）
- 表格：交易日期 | 对手方 | 类型 | 资产 / 范围 | 公开金额
- ≥ 1 条；如完全无可见交易 → 标注「近 24 月无公开 BD 交易」

## 五、团队
- 关键人物（CEO / CSO / CMO / Head of BD），以及他们的背景一句话
- 来源：web search（公司官网、LinkedIn 公开信息、新闻）

## 六、战略缺口 / 优先级（视角驱动）
- buyer 视角 → 这家 biotech 的资产 attractiveness 在哪 / 主要风险点
- seller 视角 → 这家 MNC 当前 buying priority 是什么 / pipeline gap 在哪 / 我方资产可能切入的角度
- neutral → 中性列出 strategic context，不做推荐

## 七、风险提示
- 财务 / 管线 / IP / 监管 / 团队稳定性中至少 2 条
- 来源标注

## 八、建议下一步（视角化）
- buyer → 联系 / 深度 DD / 估值
- seller → cold outreach 切入点 / pitch 角度
- neutral → 进一步研究方向
```

## 引用规范

- CRM 数据点：直接陈述即可（已知来源）
- Web search 数据点：写成「(据 [来源域名]，YYYY 报道) ...」
- 推断 / 估算：标注「(估算)」或「(待核实)」
- 完全未知：标注「⚠️ 待补充」，不要编造
"""


_PERSPECTIVE_LABEL = {
    "buyer": "买方视角（评估潜在卖方 / 资产标的）",
    "seller": "卖方视角（评估潜在买方 / 合作方）",
    "neutral": "中性视角（综合 snapshot）",
}


USER_PROMPT_TEMPLATE = """## 分析任务

- **公司**: {company}
- **视角**: {perspective_label}
- **聚焦**: {focus}
- **今天日期**: {today}

## CRM 数据

### 公司主表
{company_block}

### 资产（最多 6 条）
{assets_block}

### 相关交易（最多 8 条）
{deals_block}

## 网络检索结果

{web_block}

## 任务

按系统提示的 8 节结构生成完整 markdown。直接以 `# {company} 公司分析` 开头。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class CompanyAnalysisService(ReportService):
    slug = "company-analysis"
    display_name = "Company Analysis"
    description = (
        "公司深度分析（双向）：CRM + Web 检索 + LLM 综合，"
        "支持 buyer/seller/neutral 三视角，输出 docx + md。"
    )
    chat_tool_name = "analyze_company"
    chat_tool_description = (
        "Generate a structured BD-oriented company analysis. Supports buyer "
        "perspective (evaluating a target biotech), seller perspective "
        "(evaluating a potential MNC buyer), or neutral snapshot. Pulls "
        "CRM data + Tavily web search + single LLM synthesis. Returns "
        ".md + .docx with 8-section report. ~30-60s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "perspective": {
                "type": "string",
                "enum": ["buyer", "seller", "neutral"],
                "default": "neutral",
            },
            "focus": {
                "type": "string",
                "description": "聚焦点（自由文本），e.g. '重点看 BD 历史和管线 gap'",
            },
            "include_web_search": {"type": "boolean", "default": True},
        },
        "required": ["company_name"],
    }
    input_model = CompanyAnalysisInput
    mode = "async"
    output_formats = ["docx", "md"]
    estimated_seconds = 50
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = CompanyAnalysisInput(**params)
        today = datetime.date.today().isoformat()

        # Phase 1 — CRM lookup
        ctx.log(f"查 CRM: company='{inp.company_name}'")
        company_row = self._query_company(ctx, inp.company_name)
        assets = self._query_assets(ctx, inp.company_name)
        deals = self._query_deals(ctx, inp.company_name)
        ctx.log(
            f"CRM: 公司 {'✓' if company_row else '✗'} | "
            f"资产 {len(assets)} 条 | 交易 {len(deals)} 条"
        )

        # Phase 2 — Web search
        web_block = "(网络检索未启用)"
        if inp.include_web_search:
            ctx.log("Tavily 4 次搜索（BD / 管线 / 团队 / 财务）...")
            queries = [
                f"{inp.company_name} BD deal license acquisition partnership 2024 2025",
                f"{inp.company_name} pipeline phase clinical trial 2025",
                f"{inp.company_name} CEO CFO BD leadership team",
                f"{inp.company_name} financial revenue cash runway funding 2025",
            ]
            web = search_and_deduplicate(queries, max_results_per_query=3)
            web_block = format_web_results(web, True)
            ctx.log(f"网络检索返回 {len(web)} 条结果")

        # Phase 3 — LLM call
        ctx.log("LLM: 综合分析中...")
        user_prompt = USER_PROMPT_TEMPLATE.format(
            company=inp.company_name,
            perspective_label=_PERSPECTIVE_LABEL[inp.perspective],
            focus=inp.focus or "(无)",
            today=today,
            company_block=self._format_company_block(company_row, inp.company_name),
            assets_block=self._format_assets_block(assets),
            deals_block=self._format_deals_block(deals, inp.company_name),
            web_block=web_block,
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4500,
        )
        if not markdown or len(markdown) < 500:
            raise RuntimeError("LLM produced an empty or very short company analysis.")

        # Phase 4 — Save outputs
        slug = safe_slug(inp.company_name) or "company"
        md_filename = f"company_{slug}_{inp.perspective}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown 已保存")

        ctx.log("渲染 Word 文档...")
        doc = docx_builder.new_report_document()
        docx_builder.add_title(
            doc,
            title=f"{inp.company_name} — Company Analysis",
            subtitle=_PERSPECTIVE_LABEL[inp.perspective] + f" · {today}",
        )
        docx_builder.markdown_to_docx(markdown, doc)
        docx_bytes = docx_builder.document_to_bytes(doc)
        ctx.save_file(f"company_{slug}_{inp.perspective}_{today}.docx", docx_bytes, format="docx")

        suggested_commands = self._build_suggested_commands(inp, assets)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.company_name} Company Analysis ({inp.perspective})",
                "company": inp.company_name,
                "perspective": inp.perspective,
                "crm_hit_company": bool(company_row),
                "crm_hit_assets": len(assets),
                "crm_hit_deals": len(deals),
                "suggested_commands": suggested_commands,
            },
        )

    # ── CRM queries ─────────────────────────────────────────

    def _query_company(self, ctx: ReportContext, company: str) -> dict | None:
        rows = ctx.crm_query(
            f'SELECT "客户名称", "客户类型", "所处国家", "核心产品的阶段", '
            f'"主要核心pipeline的名字", "BD跟进优先级", "客户介绍" '
            f'FROM "公司" WHERE "客户名称" ILIKE ? {LIKE_ESCAPE} LIMIT 1',
            (like_contains(company),),
        )
        return rows[0] if rows else None

    def _query_assets(self, ctx: ReportContext, company: str) -> list[dict]:
        return ctx.crm_query(
            f'SELECT "资产名称", "靶点", "作用机制(MOA)", "临床阶段", "适应症", '
            f'"差异化分级", "差异化描述", "Q总分" '
            f'FROM "资产" WHERE "所属客户" ILIKE ? {LIKE_ESCAPE} '
            f'ORDER BY "Q总分" DESC NULLS LAST LIMIT 6',
            (like_contains(company),),
        )

    def _query_deals(self, ctx: ReportContext, company: str) -> list[dict]:
        pat = like_contains(company)
        return ctx.crm_query(
            f'SELECT "交易名称", "交易类型", "买方公司", "卖方/合作方", "资产名称", '
            f'"靶点", "临床阶段", "首付款($M)", "交易总额($M)", "宣布日期" '
            f'FROM "交易" WHERE "买方公司" ILIKE ? {LIKE_ESCAPE} OR '
            f'"卖方/合作方" ILIKE ? {LIKE_ESCAPE} '
            f'ORDER BY "宣布日期" DESC LIMIT 8',
            (pat, pat),
        )

    # ── Prompt block formatters ─────────────────────────────

    def _format_company_block(self, company_row: dict | None, name: str) -> str:
        if not company_row:
            return f"⚠️ CRM 未命中 '{name}' — 全部信息需依靠网络检索"
        lines = []
        for k in (
            "客户名称",
            "客户类型",
            "所处国家",
            "核心产品的阶段",
            "主要核心pipeline的名字",
            "BD跟进优先级",
            "客户介绍",
        ):
            v = company_row.get(k)
            if v:
                lines.append(f"- **{k}**: {v}")
        return "\n".join(lines) or "(CRM 字段全空)"

    def _format_assets_block(self, assets: list[dict]) -> str:
        if not assets:
            return "(CRM 无资产记录 — 请依据网络检索补充)"
        lines = []
        for a in assets:
            name = a.get("资产名称", "?")
            target = a.get("靶点") or "-"
            phase = a.get("临床阶段") or "-"
            indication = a.get("适应症") or "-"
            diff = a.get("差异化分级") or "-"
            lines.append(
                f"- {name} | 靶点={target} | 阶段={phase} | 适应症={indication} | 差异化={diff}"
            )
        return "\n".join(lines)

    def _format_deals_block(self, deals: list[dict], company: str) -> str:
        if not deals:
            return f"(CRM 无 '{company}' 相关交易记录)"
        lines = []
        for d in deals:
            date = d.get("宣布日期") or "?"
            buyer = d.get("买方公司") or "?"
            seller = d.get("卖方/合作方") or "?"
            kind = d.get("交易类型") or "-"
            asset = d.get("资产名称") or "-"
            upfront = d.get("首付款($M)") or "-"
            total = d.get("交易总额($M)") or "-"
            lines.append(
                f"- {date} | {kind} | {buyer} ← {seller} | "
                f"资产={asset} | upfront ${upfront}M | total ${total}M"
            )
        return "\n".join(lines)

    # ── Lifecycle handoff chips ─────────────────────────────

    def _build_suggested_commands(
        self, inp: CompanyAnalysisInput, assets: list[dict]
    ) -> list[dict]:
        """After company analysis → suggest timing check + outreach.

        Map:
          all perspectives → /timing (check best outreach window)
                             + /email (cold outreach, perspective-aware)
          buyer + full asset → also /evaluate
        """
        chips: list[dict] = []
        email_perspective = inp.perspective if inp.perspective != "neutral" else "seller"

        # Timing chip — offered first (check before contacting)
        timing_cmd_parts = [
            "/timing",
            f' company_name="{inp.company_name}"',
            f" perspective={email_perspective}",
        ]
        if assets:
            lead_asset = assets[0].get("资产名称")
            if lead_asset:
                timing_cmd_parts.append(f' asset_name="{lead_asset}"')
        chips.append(
            {
                "label": "Check Outreach Timing",
                "command": "".join(timing_cmd_parts),
                "slug": "timing-advisor",
            }
        )

        # Email chip — always offered, perspective-aware
        email_cmd_parts = [
            "/email",
            f' to_company="{inp.company_name}"',
            " purpose=cold_outreach",
            f" from_perspective={email_perspective}",
        ]
        # Inject asset context if we have a clear lead
        if assets:
            lead = assets[0]
            asset_name = lead.get("资产名称")
            indication = lead.get("适应症")
            if asset_name:
                ctx_str = f"{asset_name}"
                if indication:
                    ctx_str += f" — {indication}"
                email_cmd_parts.append(f' asset_context="{ctx_str}"')
        chips.append(
            {
                "label": "Draft Cold Outreach Email",
                "command": "".join(email_cmd_parts),
                "slug": "outreach-email",
            }
        )

        # buyer perspective + we have an asset → also offer deal evaluation
        if inp.perspective == "buyer" and assets:
            lead = assets[0]
            asset_name = lead.get("资产名称")
            target = lead.get("靶点")
            indication = lead.get("适应症")
            phase = lead.get("临床阶段")
            if all([asset_name, target, indication, phase]):
                eval_cmd = (
                    f'/evaluate company_name="{inp.company_name}"'
                    f' asset_name="{asset_name}"'
                    f' target="{target}" indication="{indication}"'
                    f' phase="{phase}"'
                )
                chips.append(
                    {
                        "label": "Run Deal Evaluation",
                        "command": eval_cmd,
                        "slug": "deal-evaluator",
                    }
                )

        return chips
