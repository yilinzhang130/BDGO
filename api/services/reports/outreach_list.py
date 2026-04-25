"""
Outreach List — view BD outreach pipeline / thread history.

Reads the outreach_log event stream for the calling user and renders
either:
  - A pipeline view (no `company` filter) — per-company status counts,
    sorted by last-touched, showing what's where in the funnel
  - A thread view (with `company` filter) — chronological event list
    for that specific company

Output: single .md, no .docx. Read-only — never writes.
"""

from __future__ import annotations

import logging
from typing import Literal

import outreach_db
from pydantic import BaseModel, Field

from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class OutreachListInput(BaseModel):
    company: str | None = Field(
        None,
        description="Filter to a specific company. Omit for pipeline view across all companies.",
    )
    status: (
        Literal[
            "sent",
            "replied",
            "meeting",
            "cda_signed",
            "ts_signed",
            "definitive_signed",
            "passed",
            "dead",
        ]
        | None
    ) = None
    purpose: (
        Literal[
            "cold_outreach",
            "cda_followup",
            "data_room_request",
            "term_sheet_send",
            "meeting_request",
            "follow_up",
            "other",
        ]
        | None
    ) = None
    perspective: Literal["buyer", "seller"] | None = None
    recent_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Only events from the last N days. Omit = all-time.",
    )
    limit: int = Field(50, ge=1, le=500)


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class OutreachListService(ReportService):
    slug = "outreach-list"
    display_name = "Outreach Pipeline / Thread"
    description = (
        "查看 BD outreach 跟进记录：无 company 过滤 = pipeline 看板（按公司聚合状态），"
        "带 company = 单线程时间线。支持按状态/用途/视角/时间窗口过滤。"
    )
    chat_tool_name = "list_outreach"
    chat_tool_description = (
        "View the BD outreach pipeline (no company filter → per-company "
        "status counts) or a specific company's outreach thread (with "
        "company filter → chronological events). Read-only. Filters: "
        "status, purpose, perspective, recent_days. Returns .md."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "company": {"type": "string"},
            "status": {"type": "string", "enum": list(outreach_db.STATUSES)},
            "purpose": {"type": "string", "enum": list(outreach_db.PURPOSES)},
            "perspective": {"type": "string", "enum": list(outreach_db.PERSPECTIVES)},
            "recent_days": {"type": "integer", "minimum": 1, "maximum": 365},
            "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
        },
        "required": [],
    }
    input_model = OutreachListInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 2
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = OutreachListInput(**params)

        if not ctx.user_id:
            raise RuntimeError("Outreach list requires an authenticated user.")

        if inp.company:
            return self._render_thread(ctx, inp)
        return self._render_pipeline(ctx, inp)

    # ── Pipeline view (no company filter) ───────────────────

    def _render_pipeline(self, ctx: ReportContext, inp: OutreachListInput) -> ReportResult:
        ctx.log("Loading outreach pipeline (per-company status counts)…")
        rows = outreach_db.status_counts_per_company(
            user_id=ctx.user_id, recent_days=inp.recent_days
        )
        # Apply post-filters that don't apply at SQL grouping level
        # (we already aggregated; status filter doesn't apply here)
        markdown = self._format_pipeline_md(rows, inp)
        return ReportResult(
            markdown=markdown,
            meta={
                "title": "Outreach Pipeline",
                "view": "pipeline",
                "row_count": len(rows),
            },
        )

    def _format_pipeline_md(self, rows: list[dict], inp: OutreachListInput) -> str:
        if not rows:
            scope = f"最近 {inp.recent_days} 天" if inp.recent_days else "全部时间"
            return (
                f"# Outreach Pipeline\n\n"
                f"⚠️ 你在{scope}内还没有 outreach 记录。\n\n"
                f'用 `/log to_company="..." purpose=cold_outreach` 开始记录。\n'
            )

        # Group rows by company → {status: count, last_touched}
        by_company: dict[str, dict] = {}
        for r in rows:
            c = r["to_company"]
            if c not in by_company:
                by_company[c] = {"statuses": {}, "last_touched": r["last_touched"]}
            by_company[c]["statuses"][r["status"]] = r["n"]
            if r["last_touched"] > by_company[c]["last_touched"]:
                by_company[c]["last_touched"] = r["last_touched"]

        # Sort companies by last touched (most recent first)
        ordered = sorted(by_company.items(), key=lambda x: x[1]["last_touched"], reverse=True)

        lines = ["# Outreach Pipeline", ""]
        if inp.recent_days:
            lines.append(f"> 最近 **{inp.recent_days}** 天")
        else:
            lines.append("> 全部时间")
        lines.append(f"> 公司数: **{len(by_company)}**  ·  事件总数: {sum(r['n'] for r in rows)}")
        lines.append("")
        lines.append("| 公司 | 状态分布 | 最后更新 |")
        lines.append("|---|---|---|")

        for company, info in ordered:
            statuses = info["statuses"]
            badge = " · ".join(f"{s}={n}" for s, n in statuses.items())
            ts = info["last_touched"].strftime("%Y-%m-%d") if info["last_touched"] else "-"
            lines.append(f"| {company} | {badge} | {ts} |")

        lines.append("")
        lines.append('查单个公司的完整线程：`/outreach company="<公司名>"`')
        return "\n".join(lines) + "\n"

    # ── Thread view (with company filter) ───────────────────

    def _render_thread(self, ctx: ReportContext, inp: OutreachListInput) -> ReportResult:
        ctx.log(f"Loading thread for {inp.company}…")
        events = outreach_db.list_events(
            user_id=ctx.user_id,
            company=inp.company,
            status=inp.status,
            purpose=inp.purpose,
            perspective=inp.perspective,
            recent_days=inp.recent_days,
            limit=inp.limit,
        )
        markdown = self._format_thread_md(events, inp)
        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"Outreach thread: {inp.company}",
                "view": "thread",
                "company": inp.company,
                "row_count": len(events),
                "suggested_commands": self._thread_chips(inp),
            },
        )

    def _format_thread_md(self, events: list[dict], inp: OutreachListInput) -> str:
        if not events:
            return (
                f"# Outreach Thread — {inp.company}\n\n"
                f"⚠️ 没有匹配 `{inp.company}` 的 outreach 记录。\n"
            )

        lines = [f"# Outreach Thread — {inp.company}", ""]
        lines.append(f"> 事件数: **{len(events)}**")
        lines.append("")
        lines.append("| 日期 | 用途 | 状态 | 渠道 | 联系人 | 备注 |")
        lines.append("|---|---|---|---|---|---|")
        for e in events:
            ts = e["created_at"].strftime("%Y-%m-%d %H:%M") if e["created_at"] else "-"
            notes = (e.get("notes") or e.get("subject") or "")[:60]
            if notes and len(e.get("notes") or e.get("subject") or "") > 60:
                notes += "…"
            contact = e.get("to_contact") or "-"
            lines.append(
                f"| {ts} | {e['purpose']} | {e['status']} | {e['channel']} | {contact} | {notes} |"
            )
        return "\n".join(lines) + "\n"

    def _thread_chips(self, inp: OutreachListInput) -> list[dict]:
        """From a thread view, offer logging the most likely next status."""
        return [
            {
                "label": "Log Reply",
                "command": f'/log to_company="{inp.company}" status=replied purpose=follow_up',
                "slug": "outreach-log",
            },
            {
                "label": "Log Meeting",
                "command": f'/log to_company="{inp.company}" status=meeting purpose=meeting_request',
                "slug": "outreach-log",
            },
        ]
