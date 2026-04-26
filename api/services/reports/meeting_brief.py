"""
Meeting Brief — pre-meeting prep sheet for BD meetings.

One-page output covering:
  - Meeting context (date, format, participants)
  - Counterparty profile (their ask, hot buttons, recent moves)
  - Our objectives (what we want from this meeting)
  - Talking points (3-5 data-backed discussion topics)
  - Anticipated questions + suggested answers
  - Red lines / walk-away conditions
  - Recommended next-step ask

Input: counterparty name + meeting purpose + optional context.
Data: CRM outreach_log (prior touch history) + CRM company row + Tavily news.
Output: one .md file (~600-900 words), no .docx (designed for quick scan).
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

import outreach_db
from pydantic import BaseModel, Field, model_validator

from services.external import search
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import format_web_results, safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class MeetingBriefInput(BaseModel):
    counterparty: str = Field(
        ..., description="Company or person you're meeting (e.g. 'AstraZeneca BD team')"
    )
    meeting_purpose: Literal[
        "intro_pitch",  # first BD pitch
        "cda_negotiation",  # NDA / CDA discussion
        "data_room_review",  # scientific deep-dive / DD session
        "term_sheet",  # TS negotiation
        "partnership",  # co-dev / co-promote discussion
        "follow_up",  # general follow-up / catch-up
    ] = "intro_pitch"
    our_perspective: Literal["seller", "buyer"] = "seller"
    asset_context: str | None = Field(
        None, description="Asset name + 1-2 sentence brief. Sharpens talking points."
    )
    meeting_date: str | None = Field(
        None, description="ISO date (YYYY-MM-DD). Defaults to today if omitted."
    )
    attendees_our_side: str | None = Field(
        None, description="Our attendees, e.g. 'CEO + Head of BD + CMO'"
    )
    attendees_their_side: str | None = Field(
        None, description="Known counterparty attendees if any"
    )
    extra_context: str | None = Field(
        None, description="Prior meeting notes, recent news, specific agenda items"
    )
    include_web_search: bool = True

    @model_validator(mode="after")
    def validate_inputs(self) -> MeetingBriefInput:
        if not self.counterparty.strip():
            raise ValueError("counterparty must not be empty")
        return self


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

_PURPOSE_LABEL = {
    "intro_pitch": "Initial BD Pitch",
    "cda_negotiation": "CDA / NDA Negotiation",
    "data_room_review": "Data Room / Scientific Review",
    "term_sheet": "Term Sheet Negotiation",
    "partnership": "Partnership / Co-Dev Discussion",
    "follow_up": "Follow-up / Catch-up",
}

SYSTEM_PROMPT = """你是 BD Go 平台的会议准备专家。你的任务：基于 CRM 记录、历史 outreach 记录和网络检索，
生成一份精准、可直接使用的**会前简报（Meeting Brief）**。

读者场景：BD 在会议开始前 30 分钟快速浏览，确认自己准备到位。

硬规则：
1. **输出严格 6 节**（见下方格式），不多不少
2. **具体化** — 每条 talking point 必须引用数字、交易名称、或具体数据点
3. **反向视角** — "对方诉求"一节要真正站在对方角度思考，不要只写我方想要什么
4. **预见问题** — 他们最可能问的 3 个难题 + 推荐回答方向（不超过 1 句话/题）
5. **一句话 ask** — 最后一节必须给出会议结束时的明确 ask（e.g. "请求在 2 周内反馈是否签 CDA"）
6. **总长 600-900 字** — 简报的价值在于聚焦，不在全面
7. **中文为主**，公司名/资产名/术语保留英文
"""

_USER_PROMPT_TEMPLATE = """## 会议信息

- **对方**: {counterparty}
- **会议类型**: {purpose_label}
- **我方视角**: {perspective_label}
- **会议日期**: {meeting_date}
- **我方与会**: {our_attendees}
- **对方与会**: {their_attendees}

## 资产信息

{asset_block}

## 历史 Outreach 记录（CRM）

{outreach_history}

## 对方公司信息（CRM）

{company_info}

## 网络检索结果（对方近期动态）

{web_block}

## 其他上下文

{extra_block}

## 任务

输出一份会前简报（Meeting Brief），严格按以下 6 节格式，总长 600-900 字：

```
# 会前简报 — {counterparty} · {purpose_label} · {meeting_date}

## 1. 会议背景

（2-3 句话：我们为何开这个会 + 我们目前在谈判的哪个阶段）

## 2. 对方画像与诉求

（3-4 条 bullet：对方的战略背景 / 近期动态 / 他们来开会想得到什么 / 他们的决策逻辑）

## 3. 我方核心目标

（本次会议我们想达成的 1-2 个具体 outcome，不是"建立关系"这类虚词）

## 4. 核心 Talking Points（3-5 条）

（每条 1-2 句：数据驱动的论点，附引用来源）

## 5. 预见问题 & 应对思路

（他们最可能问的 3 个难题，每题 1 句推荐回答方向）

- **Q1**: ...  → 建议回答方向：...
- **Q2**: ...  → 建议回答方向：...
- **Q3**: ...  → 建议回答方向：...

## 6. 会议 Ask（结束时）

（一句话：会议结束时我们要主动提出的明确 ask）
```

直接输出 markdown，不加代码块包裹，不加前言。
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class MeetingBriefService(ReportService):
    slug = "meeting-brief"
    display_name = "Meeting Brief"
    description = (
        "BD 会前简报：对方画像 / 我方目标 / 核心谈话要点 / "
        "预见问题 / 明确 ask。基于 CRM outreach 历史 + 公司数据 + Web 检索，"
        "600-900 字，会议前 30 分钟速览。"
    )
    chat_tool_name = "generate_meeting_brief"
    chat_tool_description = (
        "Generate a pre-meeting BD brief for a counterparty. Pulls prior outreach "
        "history from CRM, optional web search for recent counterparty news, and "
        "produces a focused 6-section one-pager: meeting context, counterparty ask, "
        "our objectives, talking points (3-5), anticipated Q&A (3), and the closing ask. "
        "~25s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "counterparty": {
                "type": "string",
                "description": "Company or person you're meeting (e.g. 'AstraZeneca', 'Pfizer BD team').",
            },
            "meeting_purpose": {
                "type": "string",
                "enum": [
                    "intro_pitch",
                    "cda_negotiation",
                    "data_room_review",
                    "term_sheet",
                    "partnership",
                    "follow_up",
                ],
                "default": "intro_pitch",
            },
            "our_perspective": {
                "type": "string",
                "enum": ["seller", "buyer"],
                "default": "seller",
            },
            "asset_context": {
                "type": "string",
                "description": "Asset name + 1-2 sentence brief.",
            },
            "meeting_date": {
                "type": "string",
                "description": "ISO date YYYY-MM-DD (defaults to today).",
            },
            "attendees_our_side": {"type": "string"},
            "attendees_their_side": {"type": "string"},
            "extra_context": {
                "type": "string",
                "description": "Prior notes, specific agenda items, known sticking points.",
            },
            "include_web_search": {
                "type": "boolean",
                "default": True,
            },
        },
        "required": ["counterparty"],
    }
    input_model = MeetingBriefInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 25
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = MeetingBriefInput(**params)
        today = datetime.date.today().isoformat()
        meeting_date = inp.meeting_date or today

        ctx.log(f"Generating meeting brief: {inp.counterparty} · {inp.meeting_purpose}")

        # 1. CRM outreach history
        outreach_history = self._query_outreach(ctx, inp.counterparty)

        # 2. CRM company row
        company_info = self._query_company(ctx, inp.counterparty)

        # 3. Optional web search — counterparty recent news
        web_results: list[dict] = []
        if inp.include_web_search:
            ctx.log("Web search: counterparty recent news…")
            queries = [
                f"{inp.counterparty} BD deal partnership 2025 2026",
                f"{inp.counterparty} pipeline news announcement",
            ]
            if inp.asset_context:
                queries.append(f"{inp.counterparty} {inp.asset_context} deal interest")
            for q in queries:
                web_results.extend(search.tavily_search(q, max_results=3))
            ctx.log(f"Web search done: {len(web_results)} results")

        # 4. Build prompt and call LLM
        prompt = _USER_PROMPT_TEMPLATE.format(
            counterparty=inp.counterparty,
            purpose_label=_PURPOSE_LABEL[inp.meeting_purpose],
            perspective_label="卖方（我方有资产）"
            if inp.our_perspective == "seller"
            else "买方（我方寻求资产）",
            meeting_date=meeting_date,
            our_attendees=inp.attendees_our_side or "(未指定)",
            their_attendees=inp.attendees_their_side or "(未知)",
            asset_block=inp.asset_context or "(未指定具体资产 — 综合关系建设会议)",
            outreach_history=outreach_history,
            company_info=company_info,
            web_block=format_web_results(web_results, inp.include_web_search),
            extra_block=inp.extra_context or "(无)",
        )

        ctx.log("Calling LLM for meeting brief…")
        markdown = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )

        if not markdown or len(markdown.strip()) < 200:
            raise RuntimeError("LLM returned an empty or too-short meeting brief.")

        # 5. Save
        slug = safe_slug(f"{inp.counterparty}_{inp.meeting_purpose}") or "meeting"
        md_fn = f"meeting_brief_{slug}_{meeting_date}.md"
        ctx.save_file(md_fn, markdown, format="md")
        ctx.log("Meeting brief saved")

        # 6. Suggested chips
        suggested_commands = self._build_chips(inp)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"Meeting Brief — {inp.counterparty} · {_PURPOSE_LABEL[inp.meeting_purpose]}",
                "counterparty": inp.counterparty,
                "meeting_purpose": inp.meeting_purpose,
                "our_perspective": inp.our_perspective,
                "meeting_date": meeting_date,
                "suggested_commands": suggested_commands,
            },
        )

    # ── Helpers ─────────────────────────────────────────────

    def _query_outreach(self, ctx: ReportContext, counterparty: str) -> str:
        """Pull last 5 outreach events for this counterparty from CRM."""
        if not ctx.user_id:
            return "(Outreach history unavailable — no user context)"
        try:
            events = outreach_db.list_events(
                ctx.user_id,
                company=counterparty,
                limit=5,
            )
            if not events:
                return "(无 CRM outreach 记录)"
            lines = []
            for ev in events:
                date_str = str(ev.get("created_at", ""))[:10]
                lines.append(
                    f"- {date_str} · {ev.get('purpose', '?')} · status={ev.get('status', '?')}"
                    + (f" · {ev.get('notes', '')}" if ev.get("notes") else "")
                )
            return "\n".join(lines)
        except Exception:
            logger.exception("Outreach history query failed for %s", counterparty)
            return "(Outreach history query failed)"

    def _query_company(self, ctx: ReportContext, counterparty: str) -> str:
        """Pull CRM company row for basic background."""
        try:
            from crm_store import LIKE_ESCAPE, like_contains

            rows = ctx.crm_query(
                f'SELECT "客户名称", "客户类型", "所处国家", "核心产品的阶段", '
                f'"主要核心pipeline的名字", "BD跟进优先级", "客户介绍" '
                f'FROM "公司" WHERE "客户名称" ILIKE ? {LIKE_ESCAPE} LIMIT 1',
                (like_contains(counterparty),),
            )
            if not rows:
                return f"(CRM 中未找到 {counterparty} 的公司记录)"
            row = rows[0]
            parts = [f"公司: {row.get('客户名称', '?')}"]
            if row.get("客户类型"):
                parts.append(f"类型: {row['客户类型']}")
            if row.get("所处国家"):
                parts.append(f"国家: {row['所处国家']}")
            if row.get("主要核心pipeline的名字"):
                parts.append(f"核心管线: {row['主要核心pipeline的名字']}")
            if row.get("BD跟进优先级"):
                parts.append(f"BD优先级: {row['BD跟进优先级']}")
            if row.get("客户介绍"):
                parts.append(f"简介: {row['客户介绍'][:300]}")
            return " | ".join(parts)
        except Exception:
            logger.exception("Company CRM query failed for %s", counterparty)
            return f"(CRM 查询失败 — {counterparty})"

    def _build_chips(self, inp: MeetingBriefInput) -> list[dict]:
        """Post-meeting chips based on meeting purpose."""
        chips: list[dict] = []

        # Log the upcoming meeting
        log_parts = [
            "/log",
            f' to_company="{inp.counterparty}"',
            f" purpose={inp.meeting_purpose}",
            " status=meeting",
            f" perspective={inp.our_perspective}",
        ]
        if inp.asset_context:
            log_parts.append(f' asset_context="{inp.asset_context}"')
        chips.append(
            {
                "label": "Log Meeting",
                "command": "".join(log_parts),
                "slug": "outreach-log",
            }
        )

        # Purpose-specific downstream
        if inp.meeting_purpose == "data_room_review":
            chips.append(
                {
                    "label": "Run DD Checklist",
                    "command": f'/dd company="{inp.counterparty}" perspective={inp.our_perspective}',
                    "slug": "dd-checklist",
                }
            )
        elif inp.meeting_purpose == "term_sheet":
            chips.append(
                {
                    "label": "Draft Term Sheet",
                    "command": (
                        f'/draft-ts licensee="{inp.counterparty}"'
                        + (f' asset_name="{inp.asset_context}"' if inp.asset_context else "")
                    ),
                    "slug": "draft-ts",
                }
            )
        elif inp.meeting_purpose == "intro_pitch":
            chips.append(
                {
                    "label": "Draft Follow-up Email",
                    "command": (
                        f'/email to_company="{inp.counterparty}" purpose=follow_up'
                        + (f' asset_context="{inp.asset_context}"' if inp.asset_context else "")
                    ),
                    "slug": "outreach-email",
                }
            )

        return chips
