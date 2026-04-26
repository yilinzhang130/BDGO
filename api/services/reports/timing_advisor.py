"""
Timing Advisor — outreach window recommendation.

Given a target company / asset, synthesizes:
  1. Asset-level catalysts from CRM (临床 + 资产 tables) — readouts,
     IND filings, NDA submissions, regulatory milestones
  2. Industry conference calendar — JPM HC, BIO, BIO-Europe, ASCO,
     AACR, ESMO, ASH, etc. (annual recurrence; next instance computed
     from today)
  3. Single LLM call → recommended outreach window with reasoning

Used after /company analysis or /disease landscape to time a cold
outreach (`/email cold_outreach`) for maximum leverage. The point is
"don't email Lilly the week before their ASH presentation" and "do
reach out 6-8 weeks before a Phase 2 readout, before the price moves."

Output: short .md (1-2 pages) — no docx (this is decision support, not
a deliverable).
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from config import CONFERENCE_CALENDAR_PATH
from crm_store import LIKE_ESCAPE, like_contains
from pydantic import BaseModel, Field

from services.external.conference_calendar import load_calendar
from services.quality import audit_to_dict, validate_markdown
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Industry conference calendar
# ─────────────────────────────────────────────────────────────


# Annual recurring BD-relevant events. Dates are typical (month + week);
# the timing recommender computes the next future instance from today.
# Sources: public conference sites + historical BD outreach norms.
_INDUSTRY_EVENTS = [
    {
        "name": "JPMorgan Healthcare Conference",
        "short": "JPM HC",
        "month": 1,
        "approx_week": 2,  # 2nd week of January
        "city": "San Francisco",
        "category": "deal-making",
        "bd_note": "Year's biggest BD week. Pre-JPM (Nov-Dec) is intro window; post-JPM (Feb-Mar) is follow-up window.",
    },
    {
        "name": "AACR Annual Meeting",
        "short": "AACR",
        "month": 4,
        "approx_week": 2,
        "city": "varies",
        "category": "scientific-oncology",
        "bd_note": "Major oncology data drop. Pre-AACR outreach lets you reference their abstracts.",
    },
    {
        "name": "BIO International Convention",
        "short": "BIO",
        "month": 6,
        "approx_week": 2,
        "city": "varies (US)",
        "category": "deal-making",
        "bd_note": "Largest BD partnering event globally. Schedule meetings 8-10 weeks in advance via partneringONE.",
    },
    {
        "name": "ASCO Annual Meeting",
        "short": "ASCO",
        "month": 6,
        "approx_week": 1,
        "city": "Chicago",
        "category": "scientific-oncology",
        "bd_note": "Key oncology readout window. Reach out post-ASCO if their data was strong.",
    },
    {
        "name": "ESMO Congress",
        "short": "ESMO",
        "month": 9,
        "approx_week": 3,
        "city": "varies (Europe)",
        "category": "scientific-oncology",
        "bd_note": "European oncology readout peak. Good window for EU-based MNCs.",
    },
    {
        "name": "BIO-Europe",
        "short": "BIO-Europe",
        "month": 11,
        "approx_week": 1,
        "city": "varies (Europe)",
        "category": "deal-making",
        "bd_note": "European partnering counterpart to BIO. Strong for EU/Asia BD activity.",
    },
    {
        "name": "ASH Annual Meeting",
        "short": "ASH",
        "month": 12,
        "approx_week": 2,
        "city": "varies",
        "category": "scientific-hematology",
        "bd_note": "Hematology readout peak. Pre-ASH BD activity ramps in Oct-Nov.",
    },
    {
        "name": "JPMorgan Healthcare China Day",
        "short": "JPM China",
        "month": 1,
        "approx_week": 2,
        "city": "San Francisco",
        "category": "deal-making",
        "bd_note": "Sub-event during JPM HC; relevant for China-US BD.",
    },
]


def _next_instance(month: int, approx_week: int, today: datetime.date) -> datetime.date:
    """Compute the next future instance of an annual event (month + approx week)."""
    # Approx week N → day = (N-1)*7 + 4 (mid-week, Thursday-ish)
    day = min((approx_week - 1) * 7 + 4, 28)
    candidate = datetime.date(today.year, month, day)
    if candidate < today:
        candidate = datetime.date(today.year + 1, month, day)
    return candidate


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class TimingAdvisorInput(BaseModel):
    company_name: str = Field(..., description="Target company")
    asset_name: str | None = Field(None, description="Specific asset; blank = all company's assets")
    perspective: Literal["buyer", "seller"] = "seller"
    look_ahead_months: int = Field(12, ge=1, le=24)


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD Go 的资深 timing 分析师。任务：给定一个目标公司/资产 + 它的近期催化剂日程 + 行业会议日历，推荐**最佳 outreach 窗口**并说明逻辑。

## 核心原则

1. **数据驱动**：每条建议必须引用具体催化剂日期、会议日期或时间窗口。禁止"建议尽快联系"这种空话。
2. **窗口而非点**：推荐 ≥1 周宽度的窗口（如"Q2 2026 第 6-8 周"），不要给单一日期。
3. **避开雷区**：明确指出**不要**接触的时间（如"Phase 2 readout 前 2 周内"——他们在 IR pre-brief 锁定期）。
4. **对齐视角**：
   - **seller** 视角（我方有资产，pitch 对方）→ 找对方有"buying mood"的窗口（post-readout positive、pre-JPM、pre-BIO）
   - **buyer** 视角（我方想 in-license 对方资产）→ 找对方"motivated to deal"窗口（cash runway 临近、negative readout 后、需要 capital infusion）

## 关键时间逻辑

- **Phase 2 readout 前 8-10 周**：通常是 seller 主动接触最好的窗口（leverage 高，对方还没分心）
- **Phase 2 readout 后 2-4 周**（如数据正面）：buyer 主动接触最好的窗口
- **JPM 前 8 周（Nov-Dec）**：年度 deal-making 启动期
- **JPM 后 4-6 周（Feb-Mar）**：JPM 上聊过的 deal 进入正式 DD/TS 阶段
- **BIO Convention 前 8-10 周**：partneringONE 系统排日程窗口
- **大会读出周**：尽量避免 cold outreach（注意力都在大会）
- **大会摘要公开日（abstract release）前后**：摘要公开当天起的 1-2 周是 buyer 主动询价高峰（看到正面数据后想锁定 BD）。摘要公开前 3-4 周是 seller 提前发邮件埋伏的好时点（"看到您下个月的 [大会] 摘要..."）— 仅在你能从下面"会议时间表"中看到 abstract_release 具体日期时使用此策略

## 输出结构（严格按此 5 节，无多无少）

```
# {target} 接触时机建议

> **生成日期**: {today}  ·  **视角**: {perspective}

## 一、推荐窗口（≥1 个，≤3 个）

每个窗口包含：
- **窗口**：YYYY-MM-DD 至 YYYY-MM-DD（≥1 周）
- **理由**：1-2 句话，引用具体催化剂或会议
- **建议动作**：cold outreach / partnering meeting request / data-room follow-up
- **预期 leverage**：高 / 中 / 低 + 一句解释

## 二、避开窗口（≥1 个）
- 时间段 + 为什么避开（如"催化剂前 2 周对方在 IR 锁定期"）

## 三、催化剂时间表
表格：日期 | 事件 | 类型 | 确定性 | BD 含义

## 四、会议时间表（next 12 月）
表格：日期 | 会议简称 | 类型（deal-making / scientific）| 是否建议接触

## 五、整体策略一句话
（≤ 30 字总结：什么时候、做什么、为什么）
```

## 写作风格

- 中文为主，专业术语保留英文（readout, IR window, deal-making, partneringONE）
- 不写"建议您"、"我方建议"——直接陈述结论
- 不引用未给出的数据
- 如催化剂数据稀疏（< 2 条），明确标注「催化剂数据不足，建议结合行业窗口」
"""


USER_PROMPT_TEMPLATE = """## Timing 分析任务

- **目标公司**: {company}
- **资产范围**: {asset_scope}
- **视角**: {perspective_blurb}
- **今天日期**: {today}
- **看 ahead 月数**: {look_ahead_months}

## CRM 催化剂数据

{catalysts_block}

## 未来 12 个月行业会议日历

{conferences_block}

## 任务

按系统提示的 5 节结构生成完整 markdown。直接以 `# {company}{asset_suffix} 接触时机建议` 开头。
"""


_GAP_FILL_PROMPT = """以下是已生成的接触时机建议 markdown 草稿，以及 Schema 校验器发现的结构性缺陷列表。
请在**不改变已通过校验内容**的前提下，仅修补以下缺陷，输出**完整的修正后 markdown**。

=== 待修补缺陷 ===
{fail_list}

=== 原始 markdown ===
{markdown}

修补规则：
- "section_missing" → 按 5 节顺序（推荐窗口 / 避开窗口 / 催化剂时间表 / 会议时间表 / 整体策略一句话）插入缺失节
- 推荐窗口节必须含 YYYY-MM-DD 至 YYYY-MM-DD 形式的日期范围
- 避开窗口节必须明确"避开/IR 锁定/沉默期"等
- 催化剂时间表至少出现一个 readout/IND/NDA/Phase 关键词
- 会议时间表至少含一个核心 BD 会议（JPM/BIO/ASCO/AACR/ESMO/ASH 等）
- 整体策略一句话节内容应 ≤ 30 字
- 不要使用"建议尽快联系"这种空话 — 引用具体催化剂或日期
- 不要新增未列出的章节，不要删除已有内容
- 输出整个 markdown，不加任何解释或代码块包裹
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


class TimingAdvisorService(ReportService):
    slug = "timing-advisor"
    display_name = "Outreach Timing Advisor"
    description = (
        "推荐 cold outreach 最佳时机：综合 CRM 催化剂日期 + 行业会议日历，"
        "支持买/卖方视角，输出窗口建议 + 避开期 + 整体策略。"
    )
    chat_tool_name = "advise_outreach_timing"
    chat_tool_description = (
        "Recommend the optimal outreach window for cold-contacting a target "
        "company. Synthesizes CRM catalyst dates (clinical readouts, "
        "regulatory milestones) + industry conference calendar (JPM, BIO, "
        "ASCO, AACR, ESMO, ASH) into a 5-section timing report. Buyer or "
        "seller perspective. Returns .md, ~15-25s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "asset_name": {
                "type": "string",
                "description": "Specific asset; blank = all company's assets",
            },
            "perspective": {
                "type": "string",
                "enum": ["buyer", "seller"],
                "default": "seller",
            },
            "look_ahead_months": {"type": "integer", "default": 12, "minimum": 1, "maximum": 24},
        },
        "required": ["company_name"],
    }
    input_model = TimingAdvisorInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 25
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = TimingAdvisorInput(**params)
        today = datetime.date.today()
        today_str = today.isoformat()

        # Phase 1 — Pull catalysts from CRM
        ctx.log(f"查 CRM 催化剂: company='{inp.company_name}', asset='{inp.asset_name or '(any)'}'")
        catalysts = self._query_catalysts(ctx, inp.company_name, inp.asset_name)
        ctx.log(f"CRM 催化剂命中 {len(catalysts)} 条")

        # Phase 2 — Compute upcoming industry conferences
        conferences = self._compute_upcoming_conferences(today, inp.look_ahead_months)
        ctx.log(f"行业会议日历：{len(conferences)} 个未来事件")

        # Phase 3 — LLM synthesis
        ctx.log("LLM: 综合时机分析...")
        user_prompt = USER_PROMPT_TEMPLATE.format(
            company=inp.company_name,
            asset_scope=inp.asset_name or "(全部资产)",
            asset_suffix=f" — {inp.asset_name}" if inp.asset_name else "",
            perspective_blurb=self._perspective_blurb(inp.perspective),
            today=today_str,
            look_ahead_months=inp.look_ahead_months,
            catalysts_block=self._format_catalysts_block(catalysts),
            conferences_block=self._format_conferences_block(conferences),
        )
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2500,
        )
        if not markdown or len(markdown) < 300:
            raise RuntimeError("LLM produced an empty or very short timing report.")

        # Phase 4 — L0/L1 schema validation + targeted gap-fill
        # Same shape as /draft-ts (#105), /dataroom (#106),
        # /synthesize (#107), /company (#108).
        schema_audit, markdown = self._validate_and_repair(markdown, ctx)

        # Phase 5 — Save markdown (post-repair)
        slug = safe_slug(f"{inp.company_name}_{inp.asset_name or 'all'}") or "timing"
        md_filename = f"timing_{slug}_{today_str}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Markdown 已保存")

        suggested_commands = self._build_suggested_commands(inp, catalysts)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.company_name} Outreach Timing",
                "company": inp.company_name,
                "asset": inp.asset_name,
                "perspective": inp.perspective,
                "catalysts_count": len(catalysts),
                "conferences_count": len(conferences),
                "schema_audit": schema_audit,
                "suggested_commands": suggested_commands,
            },
        )

    # ── L0 + L1 quality pass ────────────────────────────────

    def _validate_and_repair(self, markdown: str, ctx: ReportContext) -> tuple[dict, str]:
        """Schema audit; if FAIL>0, one targeted gap-fill LLM pass.

        Same shape as the four prior services in this batch. Never raises.
        """
        try:
            audit = validate_markdown(markdown, mode="timing_advisor")
            ctx.log(f"Schema audit: FAIL={audit.n_fail} WARN={audit.n_warn} INFO={audit.n_info}")
            if audit.n_fail == 0:
                return audit_to_dict(audit), markdown

            ctx.log(f"L1 gap-fill: {audit.n_fail} fail(s) — targeted patch…")
            patched = ctx.llm(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_gap_fill_prompt(markdown, audit)}],
                max_tokens=3000,
                label="timing_gap_fill",
            )
            if len(patched) > 300:
                audit2 = validate_markdown(patched, mode="timing_advisor")
                ctx.log(
                    f"Post-gap-fill audit: FAIL={audit2.n_fail} "
                    f"WARN={audit2.n_warn} (was {audit.n_fail} fail)"
                )
                if audit2.n_fail < audit.n_fail:
                    schema_audit = audit_to_dict(audit2)
                    schema_audit["gap_fill_attempted"] = True
                    schema_audit["gap_fill_fail_before"] = audit.n_fail
                    schema_audit["gap_fill_fail_after"] = audit2.n_fail
                    return schema_audit, patched

                ctx.log("L1 gap-fill didn't reduce FAILs — keeping original")
            else:
                ctx.log("L1 gap-fill produced too-short output — keeping original")

            schema_audit = audit_to_dict(audit)
            schema_audit["gap_fill_attempted"] = True
            schema_audit["gap_fill_fail_before"] = audit.n_fail
            return schema_audit, markdown
        except Exception:
            logger.exception("Schema validation failed for task %s", ctx.task_id)
            return {"error": "validator_exception"}, markdown

    # ── CRM lookup ──────────────────────────────────────────

    def _query_catalysts(
        self, ctx: ReportContext, company: str, asset_name: str | None
    ) -> list[dict]:
        """Pull catalyst rows from 临床 + 资产 tables for this company/asset."""
        company_pat = like_contains(company)
        results: list[dict] = []

        # Source 1: 临床 table — richer data, has 催化剂确定性
        if asset_name:
            asset_pat = like_contains(asset_name)
            clin = ctx.crm_query(
                f'SELECT "公司名称", "资产名称", "下一个催化剂", "催化剂类型", '
                f'"催化剂预计时间", "催化剂确定性", "适应症", "临床期次" '
                f'FROM "临床" WHERE "公司名称" ILIKE ? {LIKE_ESCAPE} '
                f'AND "资产名称" ILIKE ? {LIKE_ESCAPE} '
                f'AND "催化剂预计时间" IS NOT NULL AND "催化剂预计时间" != \'\' '
                f'ORDER BY "催化剂预计时间" ASC LIMIT 10',
                (company_pat, asset_pat),
            )
        else:
            clin = ctx.crm_query(
                f'SELECT "公司名称", "资产名称", "下一个催化剂", "催化剂类型", '
                f'"催化剂预计时间", "催化剂确定性", "适应症", "临床期次" '
                f'FROM "临床" WHERE "公司名称" ILIKE ? {LIKE_ESCAPE} '
                f'AND "催化剂预计时间" IS NOT NULL AND "催化剂预计时间" != \'\' '
                f'ORDER BY "催化剂预计时间" ASC LIMIT 10',
                (company_pat,),
            )
        results.extend({**r, "_source": "clinical"} for r in clin)

        # Source 2: 资产 table — asset-level milestones
        if asset_name:
            asset_pat = like_contains(asset_name)
            ast = ctx.crm_query(
                f'SELECT "所属客户" AS "公司名称", "资产名称", "下一个临床节点" AS "下一个催化剂", '
                f'"节点预计时间" AS "催化剂预计时间", "适应症", "临床阶段" AS "临床期次" '
                f'FROM "资产" WHERE "所属客户" ILIKE ? {LIKE_ESCAPE} '
                f'AND "资产名称" ILIKE ? {LIKE_ESCAPE} '
                f'AND "节点预计时间" IS NOT NULL AND "节点预计时间" != \'\' '
                f'ORDER BY "节点预计时间" ASC LIMIT 5',
                (company_pat, asset_pat),
            )
        else:
            ast = ctx.crm_query(
                f'SELECT "所属客户" AS "公司名称", "资产名称", "下一个临床节点" AS "下一个催化剂", '
                f'"节点预计时间" AS "催化剂预计时间", "适应症", "临床阶段" AS "临床期次" '
                f'FROM "资产" WHERE "所属客户" ILIKE ? {LIKE_ESCAPE} '
                f'AND "节点预计时间" IS NOT NULL AND "节点预计时间" != \'\' '
                f'ORDER BY "节点预计时间" ASC LIMIT 5',
                (company_pat,),
            )
        results.extend(
            {**r, "_source": "asset", "催化剂确定性": "", "催化剂类型": "Milestone"} for r in ast
        )

        # Deduplicate by (asset, date) preferring 临床 source
        seen = set()
        deduped = []
        for r in results:
            key = (r.get("资产名称", ""), r.get("催化剂预计时间", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:15]

    # ── Industry conference calendar ────────────────────────

    def _compute_upcoming_conferences(
        self, today: datetime.date, look_ahead_months: int
    ) -> list[dict]:
        """Merge two sources of conference timing:

        1. ``conferences_calendar.yml`` — exact 2025/2026 conference dates
           with abstract_release dates (the BD-critical signal). Sourced
           from the conference-ingest MCP server's calendar; missing on
           prod gets [].
        2. ``_INDUSTRY_EVENTS`` — annual-recurring fallback (approximate
           week-of-month for events the calendar doesn't explicitly list,
           like JPM HC).

        Calendar entries take priority. Annual events whose short name
        already appears in the calendar are skipped to avoid double-
        counting (e.g. ASCO-2026 in calendar + "ASCO Annual Meeting"
        annual fallback).
        """
        look_ahead_days = look_ahead_months * 30
        cutoff = today + datetime.timedelta(days=look_ahead_days)

        # 1. Calendar (exact dates + abstract_release)
        from_calendar = load_calendar(
            CONFERENCE_CALENDAR_PATH,
            today=today,
            look_ahead_days=look_ahead_days,
        )

        # Track which short names the calendar already covers so the annual
        # fallback doesn't re-add the same event with a less precise date.
        covered_shorts: set[str] = set()
        for c in from_calendar:
            short = c["id"].split("-")[0].upper() if c.get("id") else ""
            if short:
                covered_shorts.add(short)

        # 2. Annual fallback for anything the calendar doesn't list
        from_annual: list[dict] = []
        for ev in _INDUSTRY_EVENTS:
            short_upper = ev["short"].split()[0].upper()  # "JPM HC" → "JPM"
            if short_upper in covered_shorts:
                continue
            d = _next_instance(ev["month"], ev["approx_week"], today)
            if d <= cutoff:
                from_annual.append(
                    {
                        **ev,
                        "date_start": d.isoformat(),
                        "abstract_release": "",  # unknown for annual approximations
                        "days_to_meeting": (d - today).days,
                        "days_to_abstract_release": None,
                        "status_label": "annual recurrence",
                        "source": "annual",
                    }
                )

        merged = from_calendar + from_annual
        merged.sort(key=lambda x: x.get("date_start", "9999"))
        return merged

    # ── Prompt formatting ───────────────────────────────────

    def _perspective_blurb(self, perspective: str) -> str:
        if perspective == "seller":
            return "卖方视角 — 我方有资产 / 能力，正在 pitch 对方（找他们 buying mood 强的窗口）"
        return "买方视角 — 我方想 in-license / 收购对方资产（找他们 motivated to deal 的窗口）"

    def _format_catalysts_block(self, catalysts: list[dict]) -> str:
        if not catalysts:
            return "(CRM 无催化剂记录 — 需依赖行业窗口判断)"
        lines = []
        for c in catalysts:
            lines.append(
                f"- {c.get('催化剂预计时间', '?')} | "
                f"资产={c.get('资产名称', '?')} | "
                f"事件={c.get('下一个催化剂', '?')} | "
                f"类型={c.get('催化剂类型', '-') or 'Milestone'} | "
                f"确定性={c.get('催化剂确定性', '-') or '-'} | "
                f"适应症={c.get('适应症', '-')} | "
                f"阶段={c.get('临床期次', '-')}"
            )
        return "\n".join(lines)

    def _format_conferences_block(self, conferences: list[dict]) -> str:
        """Format the conference block for the LLM prompt.

        Calendar-sourced rows surface the abstract-release date as a
        first-class BD signal (pre-release outreach is a key window).
        Annual-fallback rows show only the meeting date.
        """
        if not conferences:
            return "(无未来 12 月内的主要会议)"
        lines = []
        for ev in conferences:
            if ev.get("source") == "calendar":
                # Calendar entry: full BD-relevant fields
                line = (
                    f"- {ev['date_start']} | {ev.get('id', '')} ({ev.get('name', '')}) | "
                    f"TA={ev.get('ta', '?')} | 优先级={ev.get('bd_priority', '?')} | "
                    f"摘要公开={ev.get('abstract_release', '?')} | "
                    f"状态={ev.get('status_label', '?')}"
                )
                if ev.get("location"):
                    line += f" | 地点={ev['location']}"
                if ev.get("notes"):
                    line += f" | 备注：{ev['notes']}"
                lines.append(line)
            else:
                # Annual recurrence fallback: less precise
                date_str = ev.get("date_start") or ev.get("date") or "?"
                lines.append(
                    f"- {date_str} | {ev.get('short', '?')} ({ev.get('name', '?')}) | "
                    f"类别={ev.get('category', '?')} | 城市={ev.get('city', '?')} | "
                    f"BD 含义：{ev.get('bd_note', '?')}"
                )
        return "\n".join(lines)

    # ── Lifecycle handoff chips ─────────────────────────────

    def _build_suggested_commands(
        self, inp: TimingAdvisorInput, catalysts: list[dict]
    ) -> list[dict]:
        """After timing analysis → drafted email is the natural next step."""
        # Inject the asset context if available
        asset_ctx = ""
        if catalysts:
            lead = catalysts[0]
            asset_name = lead.get("资产名称", "")
            indication = lead.get("适应症", "")
            if asset_name:
                asset_ctx = f' asset_context="{asset_name}'
                if indication:
                    asset_ctx += f" — {indication}"
                asset_ctx += '"'

        email_cmd = (
            f'/email to_company="{inp.company_name}" purpose=cold_outreach'
            f" from_perspective={inp.perspective}" + asset_ctx
        )
        return [
            {
                "label": "Draft Cold Outreach Email",
                "command": email_cmd,
                "slug": "outreach-email",
            }
        ]
