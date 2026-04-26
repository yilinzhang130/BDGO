"""
Outreach Log — record a BD outreach event.

Append-only: every invocation INSERTs a new row. To "update" a thread
(recipient replied, meeting scheduled, signed CDA), invoke /log again
with the new status. The full timeline is preserved.

Used both by:
  - Humans typing `/log to_company="Pfizer" status=replied`
  - Other services chaining via meta.suggested_commands (e.g. an /email
    chip can suggest `/log status=sent` after the draft)

Output: confirmation markdown (no .docx) — this is a logging action,
not a report.
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


PurposeLit = Literal[
    "cold_outreach",
    "cda_followup",
    "data_room_request",
    "term_sheet_send",
    "meeting_request",
    "follow_up",
    "other",
]
ChannelLit = Literal["email", "linkedin", "phone", "in_person", "other"]
StatusLit = Literal[
    "sent",
    "replied",
    "meeting",
    "cda_signed",
    "ts_signed",
    "definitive_signed",
    "passed",
    "dead",
]


class OutreachLogInput(BaseModel):
    to_company: str = Field(..., description="Recipient organization")
    purpose: PurposeLit = "cold_outreach"
    status: StatusLit = "sent"
    channel: ChannelLit = "email"
    to_contact: str | None = Field(
        None, description="Specific person, e.g. 'Sarah Chen, Head of External Innovation'"
    )
    asset_context: str | None = Field(None, description="Asset name + indication")
    perspective: Literal["buyer", "seller"] | None = None
    subject: str | None = Field(None, description="Email subject if applicable")
    notes: str | None = Field(None, description="Free-form notes about this event")


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class OutreachLogService(ReportService):
    slug = "outreach-log"
    display_name = "Outreach Log"
    description = (
        "记录一次 BD outreach 事件（cold email、对方回复、签 CDA 等）。"
        "追加写入，时间线保留。状态变化时再 /log 一条新事件，不要 update。"
    )
    chat_tool_name = "log_outreach_event"
    chat_tool_description = (
        "Record a BD outreach event for the user's outreach tracker. "
        "Append-only: each call inserts one row. Status changes are "
        "logged as new events (don't UPDATE prior rows). Use this after "
        "drafting an /email, when a recipient replies, when a CDA is "
        "signed, or to mark a thread dead."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "to_company": {"type": "string"},
            "purpose": {
                "type": "string",
                "enum": list(outreach_db.PURPOSES),
                "default": "cold_outreach",
            },
            "status": {
                "type": "string",
                "enum": list(outreach_db.STATUSES),
                "default": "sent",
            },
            "channel": {
                "type": "string",
                "enum": list(outreach_db.CHANNELS),
                "default": "email",
            },
            "to_contact": {"type": "string"},
            "asset_context": {"type": "string"},
            "perspective": {"type": "string", "enum": list(outreach_db.PERSPECTIVES)},
            "subject": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["to_company"],
    }
    input_model = OutreachLogInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 2
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = OutreachLogInput(**params)

        if not ctx.user_id:
            raise RuntimeError(
                "Outreach logging requires an authenticated user. ctx.user_id is None — "
                "the dispatcher did not propagate user context."
            )

        ctx.log(f"Recording outreach event: {inp.purpose}/{inp.status} → {inp.to_company}")

        new_id = outreach_db.insert_event(
            user_id=ctx.user_id,
            to_company=inp.to_company,
            purpose=inp.purpose,
            status=inp.status,
            channel=inp.channel,
            to_contact=inp.to_contact,
            asset_context=inp.asset_context,
            perspective=inp.perspective,
            subject=inp.subject,
            notes=inp.notes,
            session_id=None,
        )

        ctx.log(f"✓ Logged event #{new_id}")

        markdown = self._format_confirmation(inp, new_id)
        suggested_commands = self._build_suggested_commands(inp)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"Logged: {inp.purpose} → {inp.to_company} ({inp.status})",
                "event_id": new_id,
                "to_company": inp.to_company,
                "purpose": inp.purpose,
                "status": inp.status,
                "suggested_commands": suggested_commands,
            },
        )

    # ── Helpers ─────────────────────────────────────────────

    def _format_confirmation(self, inp: OutreachLogInput, event_id: int) -> str:
        lines = [
            f"# ✓ Outreach event #{event_id} 已记录",
            "",
            f"- **To**: {inp.to_company}" + (f" · {inp.to_contact}" if inp.to_contact else ""),
            f"- **Purpose**: {inp.purpose}  ·  **Status**: {inp.status}  ·  **Channel**: {inp.channel}",
        ]
        if inp.perspective:
            lines.append(f"- **Perspective**: {inp.perspective}")
        if inp.asset_context:
            lines.append(f"- **Asset**: {inp.asset_context}")
        if inp.subject:
            lines.append(f"- **Subject**: {inp.subject}")
        if inp.notes:
            lines.append(f"- **Notes**: {inp.notes}")
        lines.extend(
            [
                "",
                f'查看完整跟进历史：`/outreach company="{inp.to_company}"`',
            ]
        )
        return "\n".join(lines) + "\n"

    def _build_suggested_commands(self, inp: OutreachLogInput) -> list[dict]:
        """Status-driven next-step chips after a log event.

        sent → /outreach company=X (review thread)
        replied → /log status=meeting (next event likely)
        cda_signed → /dd (run DD checklist)
        ts_signed → /legal contract_type=license (definitive)
        passed/dead → no chip
        """
        if inp.status == "cda_signed":
            return [
                {
                    "label": "Run DD Checklist",
                    "command": f'/dd company="{inp.to_company}"',
                    "slug": "dd-checklist",
                }
            ]
        if inp.status == "ts_signed":
            # After TS signed, the BD's natural next step is to *draft* the
            # definitive License Agreement. Route to /draft-license, not
            # /legal review — review needs contract text, which doesn't
            # exist yet (we're drafting it). Previously this chip claimed
            # "Draft" but fired /legal review, leaving the user stuck.
            #
            # Pre-fill what we can from the log context:
            #   perspective=seller → we sell → our_role=licensor, licensee=to_company
            #   perspective=buyer  → we buy  → our_role=licensee, licensor=to_company
            #   perspective=None   → default to seller (most common BD pattern)
            our_role = "licensee" if inp.perspective == "buyer" else "licensor"
            counterparty_role = "licensor" if our_role == "licensee" else "licensee"
            cmd_parts = [
                "/draft-license",
                f' {counterparty_role}="{inp.to_company}"',
                f" our_role={our_role}",
            ]
            if inp.asset_context:
                cmd_parts.append(f' asset_name="{inp.asset_context}"')
            return [
                {
                    "label": "Draft License Agreement",
                    "command": "".join(cmd_parts),
                    "slug": "draft-license",
                }
            ]
        if inp.status in ("sent", "replied", "meeting"):
            return [
                {
                    "label": "View Thread",
                    "command": f'/outreach company="{inp.to_company}"',
                    "slug": "outreach-list",
                }
            ]
        return []
