"""
Import Reply — paste an inbound email reply, auto-log it to outreach.

Closes the manual gap where every status update required the user to
type `/log to_company=... status=... purpose=...`. With this service:

  1. User pastes the raw email body (forwarded reply, copy from Gmail, etc.)
  2. Single LLM call extracts: counterparty company, contact, status,
     purpose, subject, key points, inferred next action
  3. Service INSERTs a row into outreach_log (append-only — same data
     model as /log)
  4. Returns confirmation markdown + status-driven lifecycle chips

Output: confirmation .md (no .docx — this is a logging shortcut, not a
deliverable). The companion /log service stays as the manual entry point;
this is the "I have raw text, do the parsing for me" flavor.

Auth: requires ctx.user_id like /log.
"""

from __future__ import annotations

import logging
from typing import Literal

import outreach_db
from pydantic import BaseModel, Field

from services.external.llm import _extract_json_object
from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class ImportReplyInput(BaseModel):
    reply_text: str = Field(
        ...,
        min_length=20,
        max_length=20_000,
        description="Raw email reply text (subject line + body + signature, all together).",
    )
    to_company_hint: str | None = Field(
        None,
        description="Override for the recipient company if the LLM gets it wrong.",
    )
    perspective: Literal["buyer", "seller"] | None = Field(
        None,
        description="Whose POV. If omitted, LLM tries to infer.",
    )
    notes_prefix: str | None = Field(
        None,
        description="Free-text prefix to prepend to the auto-extracted notes.",
    )


# ─────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """你是 BD outreach 邮件解析助手。任务：从一封收到的邮件回信里抽取结构化字段，用于自动记录到 outreach 跟踪系统。

## 硬规则

1. **只输出 JSON**，无围栏、无解释、无前后文字
2. **找不到的字段写空字符串 ""，不要编造**
3. **Status 必须是这几个之一**（基于邮件语气推断）：
   - `replied` — 对方回复但未明确下一步（最常见）
   - `meeting` — 对方同意 / 提议开会
   - `cda_signed` — 对方已签 CDA / NDA（提到签字、附件、生效）
   - `ts_signed` — 对方已签 TS / LOI
   - `definitive_signed` — 已签 license / co-dev / SPA
   - `passed` — 对方明确拒绝 / 不感兴趣 / 拒绝 deal
   - `dead` — 对方长期不回复（这种邮件不会出现，但保留）
4. **Purpose 必须是这几个之一**（推断对方在邮件里关注什么）：
   - `cold_outreach` — 初次回复
   - `cda_followup` — 围绕 CDA / NDA 讨论
   - `data_room_request` — 索要 / 提供数据室
   - `term_sheet_send` — 围绕 TS 讨论
   - `meeting_request` — 约会议
   - `follow_up` — 一般跟进
   - `other` — 都不像

## 输出 JSON Schema

```
{
  "to_company": "string",          // 发件人所在公司（不是收件人！我们要记录是哪家公司回了我们）
  "to_contact": "string",          // 发件人姓名 + 职位（如能识别）
  "subject": "string",             // 主题行（"Re: ..." 也保留）
  "status": "replied",             // 见上 7 选 1
  "purpose": "follow_up",          // 见上 7 选 1
  "summary": "string",             // 3-5 句话总结邮件要点
  "key_dates": ["YYYY-MM-DD ..."], // 邮件中明确提到的日期（截止日 / 会议日 / 数据 readout）
  "next_action": "string"          // 一句话：我们应该做什么
}
```

## 推断技巧

- 主题行通常带 "Re:" / "RE:" / "Fwd:" → 抽掉这些前缀拿核心
- 签名块通常在最后，带公司名 + 职位
- "Looking forward to..." / "Happy to discuss..." → status=replied
- "Could you send the CDA?" → status=replied, purpose=cda_followup
- "Let's schedule a call next week" → status=meeting, purpose=meeting_request
- "We've decided to pass on this" → status=passed, purpose=other
- "Please find the executed CDA attached" → status=cda_signed, purpose=cda_followup

## 注意

- 邮件可能是英文 / 中文 / 中英混合 — JSON 字段值可保留原语言
- 如果同一封邮件里既同意开会又索要数据 → status 选更进一步的（meeting > replied）
- 不要 hallucinate 公司名 — 实在抽不出就写空字符串，让人手动补
"""


USER_PROMPT_TEMPLATE = """## 待解析邮件

{reply_text}

## 任务

按 schema 输出 JSON。只输出 JSON。"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class ImportReplyService(ReportService):
    slug = "import-reply"
    display_name = "Import Outreach Reply"
    description = (
        "粘贴一封 BD outreach 邮件回信 → LLM 抽公司/状态/要点 → 自动记录到 "
        "outreach_log（append-only）。比手动 /log 快 10 倍，可错时手动改。"
    )
    chat_tool_name = "import_outreach_reply"
    chat_tool_description = (
        "Parse a raw inbound email reply (paste the full body, subject + "
        "signature included) and auto-log it as a new outreach event. "
        "LLM extracts counterparty / status / purpose / summary / next "
        "action; service INSERTs into outreach_log. Hint overrides if "
        "the LLM mis-identifies the company. Returns confirmation .md."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "reply_text": {
                "type": "string",
                "description": "Raw email body (subject + body + signature).",
            },
            "to_company_hint": {
                "type": "string",
                "description": "Override if LLM mis-identifies the counterparty.",
            },
            "perspective": {
                "type": "string",
                "enum": ["buyer", "seller"],
            },
            "notes_prefix": {
                "type": "string",
                "description": "Optional prefix to prepend to extracted notes.",
            },
        },
        "required": ["reply_text"],
    }
    input_model = ImportReplyInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 8
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = ImportReplyInput(**params)

        if not ctx.user_id:
            raise RuntimeError("Import-reply requires an authenticated user.")

        ctx.log("Parsing reply text via LLM…")
        raw = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(reply_text=inp.reply_text[:18_000]),
                }
            ],
            max_tokens=600,
            label="import_reply",
        )
        parsed = _extract_json_object(raw)
        if not parsed:
            raise RuntimeError("LLM did not return parseable JSON. Raw head: " + (raw or "")[:300])

        # Apply hint override + normalize
        company = (inp.to_company_hint or parsed.get("to_company") or "").strip()
        if not company:
            raise RuntimeError(
                "Couldn't identify a counterparty company from the reply. "
                'Re-run with to_company_hint="<company name>".'
            )

        status = self._normalize_status(parsed.get("status"))
        purpose = self._normalize_purpose(parsed.get("purpose"))
        contact = (parsed.get("to_contact") or "").strip() or None
        subject = (parsed.get("subject") or "").strip() or None
        summary = (parsed.get("summary") or "").strip()
        next_action = (parsed.get("next_action") or "").strip()
        key_dates = parsed.get("key_dates") or []

        notes = self._compose_notes(inp.notes_prefix, summary, next_action, key_dates)

        # Phase 2 — Insert event
        ctx.log(f"Inserting outreach event: {company} / {status} / {purpose}")
        new_id = outreach_db.insert_event(
            user_id=ctx.user_id,
            to_company=company,
            purpose=purpose,
            status=status,
            channel="email",
            to_contact=contact,
            asset_context=None,  # not extracted; user can edit via /log later
            perspective=inp.perspective,
            subject=subject,
            notes=notes,
            session_id=None,
        )
        ctx.log(f"✓ Logged event #{new_id}")

        markdown = self._format_confirmation(
            event_id=new_id,
            company=company,
            contact=contact,
            status=status,
            purpose=purpose,
            subject=subject,
            summary=summary,
            next_action=next_action,
            key_dates=key_dates,
            llm_used_hint=bool(inp.to_company_hint),
        )

        suggested_commands = self._build_suggested_commands(
            company=company, status=status, perspective=inp.perspective
        )

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"Imported reply: {company} ({status})",
                "event_id": new_id,
                "to_company": company,
                "status": status,
                "purpose": purpose,
                "suggested_commands": suggested_commands,
            },
        )

    # ── Normalization ───────────────────────────────────────

    def _normalize_status(self, raw: str | None) -> str:
        if not raw:
            return "replied"
        candidate = str(raw).strip().lower()
        if candidate in outreach_db.STATUSES:
            return candidate
        # Map common LLM variants
        aliases = {
            "responded": "replied",
            "interested": "replied",
            "scheduled": "meeting",
            "meeting_scheduled": "meeting",
            "rejected": "passed",
            "declined": "passed",
            "no_interest": "passed",
            "signed": "cda_signed",  # ambiguous; cda is the most likely
            "nda_signed": "cda_signed",
        }
        return aliases.get(candidate, "replied")

    def _normalize_purpose(self, raw: str | None) -> str:
        if not raw:
            return "follow_up"
        candidate = str(raw).strip().lower()
        if candidate in outreach_db.PURPOSES:
            return candidate
        return "follow_up"

    def _compose_notes(
        self,
        prefix: str | None,
        summary: str,
        next_action: str,
        key_dates: list,
    ) -> str:
        parts = []
        if prefix:
            parts.append(prefix.strip())
        if summary:
            parts.append(f"Summary: {summary}")
        if next_action:
            parts.append(f"Next: {next_action}")
        if key_dates:
            dates_str = ", ".join(str(d) for d in key_dates if d)
            if dates_str:
                parts.append(f"Dates: {dates_str}")
        return " | ".join(parts) if parts else ""

    # ── Output composition ─────────────────────────────────

    def _format_confirmation(
        self,
        *,
        event_id: int,
        company: str,
        contact: str | None,
        status: str,
        purpose: str,
        subject: str | None,
        summary: str,
        next_action: str,
        key_dates: list,
        llm_used_hint: bool,
    ) -> str:
        lines = [
            f"# ✓ 邮件已解析并记录（event #{event_id}）",
            "",
            f"- **From**: {company}" + (f" · {contact}" if contact else ""),
            f"- **Status**: `{status}`  ·  **Purpose**: `{purpose}`",
        ]
        if subject:
            lines.append(f"- **Subject**: {subject}")
        if llm_used_hint:
            lines.append("- ℹ️ 使用了 `to_company_hint` 覆盖 LLM 识别")
        lines.append("")
        if summary:
            lines.append(f"## 邮件要点\n\n{summary}\n")
        if next_action:
            lines.append(f"## 推断下一步\n\n{next_action}\n")
        if key_dates:
            dates_str = "、".join(str(d) for d in key_dates if d)
            if dates_str:
                lines.append(f"## 关键日期\n\n{dates_str}\n")
        lines.append(
            f'查完整线程：`/outreach company="{company}"`  ·  '
            f"如解析有误，用 `/log` 手工补一行覆盖。"
        )
        return "\n".join(lines) + "\n"

    # ── Lifecycle chips ─────────────────────────────────────

    def _build_suggested_commands(
        self,
        *,
        company: str,
        status: str,
        perspective: Literal["buyer", "seller"] | None = None,
    ) -> list[dict]:
        """Reuse the same status-driven chip mapping as /log."""
        chips: list[dict] = [
            {
                "label": "View Thread",
                "command": f'/outreach company="{company}"',
                "slug": "outreach-list",
            }
        ]
        if status == "cda_signed":
            chips.append(
                {
                    "label": "Run DD Checklist",
                    "command": f'/dd company="{company}"',
                    "slug": "dd-checklist",
                }
            )
        elif status == "ts_signed":
            # After TS signed, the BD's natural next step is to *draft* the
            # definitive License Agreement. Route to /draft-license, not
            # /legal review — review needs contract text, which doesn't
            # exist yet (we're drafting it). Previously this chip claimed
            # "Draft" but fired /legal review, leaving the user stuck.
            our_role = "licensee" if perspective == "buyer" else "licensor"
            counterparty_role = "licensor" if our_role == "licensee" else "licensee"
            chips.append(
                {
                    "label": "Draft License Agreement",
                    "command": (
                        f'/draft-license {counterparty_role}="{company}" our_role={our_role}'
                    ),
                    "slug": "draft-license",
                }
            )
        elif status == "meeting":
            chips.append(
                {
                    "label": "Prepare Meeting (DD prep)",
                    "command": f'/dd company="{company}"',
                    "slug": "dd-checklist",
                }
            )
        return chips
