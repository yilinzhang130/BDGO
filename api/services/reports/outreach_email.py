"""
Outreach Email — bidirectional BD outreach drafter.

Drafts a single, copy-pastable email tailored to BD lifecycle context:

  - cold_outreach        first-touch pitch / inquiry
  - cda_followup         push for CDA after initial interest
  - data_room_request    request access to data room (post-CDA)
  - term_sheet_send      sending TS for review
  - meeting_request      schedule a call / face-to-face
  - follow_up            generic nudge

Works for both perspectives:
  - from_perspective="seller" → 我方有资产 want to license/sell
  - from_perspective="buyer"  → 我方想要资产 (in-license / acquire)

Output: one markdown file with `Subject:` line + body, ready to paste
into Gmail / Outlook. No docx — these are short and the value is in
fast iteration, not formatting.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from pydantic import BaseModel, Field

from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


_PURPOSES = (
    "cold_outreach",
    "cda_followup",
    "data_room_request",
    "term_sheet_send",
    "meeting_request",
    "follow_up",
)

_PURPOSE_LABEL = {
    "cold_outreach": "Cold Outreach / First Touch",
    "cda_followup": "CDA Follow-up",
    "data_room_request": "Data Room Access Request",
    "term_sheet_send": "Term Sheet Delivery",
    "meeting_request": "Meeting Request",
    "follow_up": "Generic Follow-up / Nudge",
}


class OutreachEmailInput(BaseModel):
    to_company: str = Field(..., description="Recipient organization")
    purpose: Literal[
        "cold_outreach",
        "cda_followup",
        "data_room_request",
        "term_sheet_send",
        "meeting_request",
        "follow_up",
    ] = "cold_outreach"
    from_perspective: Literal["buyer", "seller"] = "seller"
    asset_context: str | None = Field(
        None,
        description="Asset name + 1-2 sentence brief. Drives personalization.",
    )
    from_company: str | None = None
    from_name: str | None = None
    from_role: str | None = None  # e.g. "Head of BD", "VP Business Development"
    to_name: str | None = None  # If known, e.g. "Dr. Sarah Chen"
    to_role: str | None = None  # e.g. "Head of External Innovation"
    tone: Literal["formal", "warm"] = "formal"
    language: Literal["en", "zh"] = "en"
    extra_context: str | None = Field(
        None,
        description=(
            "Free-form context: prior interaction history, recent counterparty news, "
            "deal terms already discussed, specific asks. Improves personalization."
        ),
    )


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are a senior BD professional drafting a single outreach email for a biotech business-development workflow.

# Hard rules

1. **Output exactly two parts**: a `Subject: ...` line, blank line, then the email body. No commentary, no markdown headers, no preface.
2. **Length**: 80–180 words for the body. Cold outreach skews shorter, term-sheet sends and follow-ups can run longer.
3. **No clichés**: never use "I hope this email finds you well", "circling back", "touching base", "synergy", "leverage", "reach out". If you catch yourself writing one, rewrite the sentence.
4. **Specificity over enthusiasm**: every claim must reference a concrete asset, indication, target, mechanism, deal precedent, or piece of public data. No "exciting opportunity" language without a number behind it.
5. **One ask per email**: end with one clear, time-bounded next step ("a 20-min call next week", "your CDA template", "feedback on the attached TS by Friday").
6. **Subject line**: ≤ 9 words, references the specific asset or topic, never starts with "Re:" or "FYI:".
7. **No fake urgency**: don't fabricate competing interest, deadlines, or insider knowledge you don't have.
8. **Buyer vs seller framing**:
   - Seller perspective → you are pitching an asset / capability. Lead with the asset's differentiation.
   - Buyer perspective → you are inquiring about an asset they own. Lead with what attracted you and what you're seeking.
9. **Honor the language flag**: en = English, zh = 中文（专业术语保留英文，e.g. ORR, CDA, term sheet, IND）.
10. **Tone flag**: `formal` = neutral professional. `warm` = first-name basis where appropriate, lighter sentence structure, but still no clichés.

# Anti-patterns to avoid

- Asking "would love to learn more about your priorities" with no specific ask
- Listing 5 of your assets / capabilities ("we work in oncology, immunology, neuro, …")
- Mentioning your fund / company size as a credential without tying it to the recipient
- Apologizing for the cold email
- "Looking forward to hearing from you" — replace with concrete next step

# Output format

```
Subject: <short, specific subject>

<body — 80-180 words, ending with one clear ask>

<sign-off + signature block>
```
"""


# Per-purpose framing fragments slotted into the user prompt.
_PURPOSE_FRAGMENTS = {
    "cold_outreach": (
        "First touch — recipient has no prior context. Earn the next reply: "
        "lead with one specific reason this asset / company is relevant to them "
        "(based on their recent BD activity, pipeline gap, or stated focus area). "
        "Ask for a 20-min intro call OR a CDA, not both."
    ),
    "cda_followup": (
        "Initial interest exists — they've responded but the CDA isn't yet signed. "
        "Goal is to push the CDA over the line. Reference the specific data they "
        "asked about and what they'll see post-CDA. Offer to use their CDA template "
        "to remove friction."
    ),
    "data_room_request": (
        "CDA is signed. Now requesting structured access: clinical CSRs, CMC pkg, "
        "IP filings, regulatory correspondence. Be specific about what categories "
        "you need and why each one. Propose a 30-min walkthrough call."
    ),
    "term_sheet_send": (
        "Sending a term sheet for review. Frame the deal logic in 1-2 sentences "
        "(why these terms reflect the asset's risk-adjusted value), call out the "
        "two or three terms most worth their attention, and propose a target "
        "review window (e.g. 'feedback by next Friday')."
    ),
    "meeting_request": (
        "Scheduling a working session — assume both sides are aligned to meet. "
        "Propose 2-3 concrete time slots, name the attendees from your side, "
        "and list the 3 topics you want to cover. Attach an agenda mentally."
    ),
    "follow_up": (
        "Generic nudge after silence. Keep it short (≤ 100 words), reference the "
        "specific last touchpoint, offer one new piece of information (e.g. data "
        "readout, conference deadline, comparable deal), and re-state the ask."
    ),
}


USER_PROMPT_TEMPLATE = """## Email task

- **Purpose**: {purpose} — {purpose_blurb}
- **From perspective**: {perspective_blurb}
- **Today**: {today}

## Parties

- **From**: {from_company} · {from_name} · {from_role}
- **To**: {to_company} · {to_name} · {to_role}

## Asset / topic

{asset_block}

## Tone & language

- **Tone**: {tone}
- **Language**: {language}

## Additional context

{extra_block}

## Task

Write the email. Output only `Subject:` line + blank line + body + sign-off + signature. No commentary.
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class OutreachEmailService(ReportService):
    slug = "outreach-email"
    display_name = "Outreach Email Drafter"
    description = (
        "起草 BD outreach 邮件：6 种用途（cold / CDA followup / data room / "
        "TS send / meeting / follow-up），双向（买/卖方），中英双语，含个性化上下文。"
    )
    chat_tool_name = "draft_outreach_email"
    chat_tool_description = (
        "Draft a single outreach email for a biotech BD workflow. Supports buyer "
        "or seller perspective, six lifecycle-aware purposes (cold outreach, CDA "
        "followup, data-room request, term-sheet send, meeting request, generic "
        "follow-up), formal/warm tone, English/Chinese. Returns a single .md "
        "with `Subject:` line + body, ~10-20s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "to_company": {"type": "string"},
            "purpose": {
                "type": "string",
                "enum": list(_PURPOSES),
                "default": "cold_outreach",
            },
            "from_perspective": {
                "type": "string",
                "enum": ["buyer", "seller"],
                "default": "seller",
            },
            "asset_context": {
                "type": "string",
                "description": "Asset name + 1-2 sentence brief.",
            },
            "from_company": {"type": "string"},
            "from_name": {"type": "string"},
            "from_role": {"type": "string"},
            "to_name": {"type": "string"},
            "to_role": {"type": "string"},
            "tone": {"type": "string", "enum": ["formal", "warm"], "default": "formal"},
            "language": {"type": "string", "enum": ["en", "zh"], "default": "en"},
            "extra_context": {
                "type": "string",
                "description": "Prior interaction history, news, specific asks.",
            },
        },
        "required": ["to_company"],
    }
    input_model = OutreachEmailInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 20
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = OutreachEmailInput(**params)
        today = datetime.date.today().isoformat()

        ctx.log(f"Drafting {inp.purpose} email to {inp.to_company} ({inp.from_perspective})…")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            purpose=_PURPOSE_LABEL[inp.purpose],
            purpose_blurb=_PURPOSE_FRAGMENTS[inp.purpose],
            perspective_blurb=self._perspective_blurb(inp.from_perspective),
            today=today,
            from_company=inp.from_company or "(unspecified)",
            from_name=inp.from_name or "(unspecified)",
            from_role=inp.from_role or "(unspecified)",
            to_company=inp.to_company,
            to_name=inp.to_name or "(unspecified)",
            to_role=inp.to_role or "(unspecified)",
            asset_block=self._asset_block(inp),
            tone=inp.tone,
            language=inp.language,
            extra_block=inp.extra_context or "(none)",
        )

        body = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=900,
        )

        if not body or len(body.strip()) < 60:
            raise RuntimeError("LLM produced an empty or too-short email draft.")

        # Wrap into a markdown doc with metadata header so the saved file is
        # self-documenting when downloaded outside chat.
        markdown = self._compose_markdown(inp, body, today)

        slug = safe_slug(f"{inp.to_company}_{inp.purpose}") or "email"
        md_filename = f"email_{slug}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log("Email draft saved")

        suggested_commands = self._build_suggested_commands(inp)

        return ReportResult(
            markdown=markdown,
            meta={
                "title": f"{inp.purpose} email → {inp.to_company}",
                "to_company": inp.to_company,
                "purpose": inp.purpose,
                "from_perspective": inp.from_perspective,
                "tone": inp.tone,
                "language": inp.language,
                "suggested_commands": suggested_commands,
            },
        )

    # ── Helpers ─────────────────────────────────────────────

    def _perspective_blurb(self, perspective: str) -> str:
        if perspective == "seller":
            return (
                "We are the SELLER — we own the asset / capability and are reaching out "
                "to a potential buyer / partner / licensee."
            )
        return (
            "We are the BUYER — we are interested in an asset / capability the recipient "
            "owns and are reaching out to express interest / initiate dialogue."
        )

    def _asset_block(self, inp: OutreachEmailInput) -> str:
        if inp.asset_context:
            return inp.asset_context
        return "(no specific asset — generic relationship outreach)"

    def _compose_markdown(self, inp: OutreachEmailInput, body: str, today: str) -> str:
        meta_header = (
            f"<!-- BD Go Outreach Email · generated {today}\n"
            f"     to: {inp.to_company} · purpose: {inp.purpose}"
            f" · perspective: {inp.from_perspective}"
            f" · lang: {inp.language} · tone: {inp.tone} -->\n\n"
        )
        return meta_header + body.strip() + "\n"

    def _build_suggested_commands(self, inp: OutreachEmailInput) -> list[dict]:
        """Lifecycle next-step chips after an outreach email is drafted.

        Universal first chip: /log this event so it shows up in the
        outreach pipeline. Then purpose-specific downstream chip.
        """
        # Build the /log chip — applies to every purpose
        log_parts = [
            "/log",
            f' to_company="{inp.to_company}"',
            f" purpose={inp.purpose}",
            " status=sent",
            f" perspective={inp.from_perspective}",
        ]
        if inp.asset_context:
            log_parts.append(f' asset_context="{inp.asset_context}"')
        log_chip = {
            "label": "Log as Sent",
            "command": "".join(log_parts),
            "slug": "outreach-log",
        }

        # Purpose-specific downstream
        downstream: list[dict] = []
        if inp.purpose == "cold_outreach":
            downstream.append(
                {
                    "label": "Draft CDA / NDA",
                    "command": (
                        f'/legal contract_type=cda party_position="乙方"'
                        f' counterparty="{inp.to_company}"'
                    ),
                    "slug": "legal-review",
                }
            )
        elif inp.purpose == "cda_followup":
            downstream.append(
                {
                    "label": "Run DD Checklist",
                    "command": f'/dd company="{inp.to_company}"',
                    "slug": "dd-checklist",
                }
            )
        # data_room / term_sheet_send / meeting_request / follow_up: no extra chip

        return [log_chip] + downstream
