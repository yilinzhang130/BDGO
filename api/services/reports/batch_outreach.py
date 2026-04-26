"""
Batch Outreach Email — generate personalized cold outreach to N companies in one shot.

S2-09: users coming off a /buyers result often need to reach 5–10 MNCs.
Previously this required calling /email five separate times.  BatchOutreach
accepts a list of companies + shared asset context, generates one email per
company in a single LLM call (fast, cheap), auto-logs every email to the
outreach pipeline, and returns a single markdown file the user can review
and dispatch.

Design choices:
  - One LLM call with structured multi-email output (vs. N parallel calls)
    because prompt re-use within a single context is more token-efficient
    and avoids thundering-herd issues with the API key pool.
  - Each email section is delimited by `===EMAIL:<company>===` so the
    frontend can split and display them as individual cards if desired.
  - Auto-log: each email is recorded in outreach_db (status="draft" so the
    user knows these haven't actually been sent yet — unlike /email which
    sets status="sent" because the draft is the deliverable).
  - Max 10 companies per batch to keep output tokens under ~8000.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

import outreach_db
from pydantic import BaseModel, Field, field_validator

from services.report_builder import (
    ReportContext,
    ReportResult,
    ReportService,
)
from services.text import safe_slug

logger = logging.getLogger(__name__)

_MAX_COMPANIES = 10

# ─────────────────────────────────────────────────────────────
# Input model
# ─────────────────────────────────────────────────────────────


class BatchOutreachInput(BaseModel):
    companies: list[str] = Field(
        ...,
        description=(
            f"List of company names to email (max {_MAX_COMPANIES}). "
            "Typically pulled from a /buyers result."
        ),
        min_length=1,
    )
    purpose: Literal[
        "cold_outreach",
        "meeting_request",
        "follow_up",
    ] = "cold_outreach"
    from_perspective: Literal["buyer", "seller"] = "seller"
    asset_context: str | None = Field(
        None,
        description="Asset name + 1-2 sentence brief. Used to personalize each email.",
    )
    from_company: str | None = None
    from_name: str | None = None
    from_role: str | None = None
    tone: Literal["formal", "warm"] = "formal"
    language: Literal["en", "zh"] = "en"
    extra_context: str | None = Field(
        None,
        description="Any shared context relevant to all emails: prior contacts, event hooks, etc.",
    )

    @field_validator("companies")
    @classmethod
    def _validate_companies(cls, v: list[str]) -> list[str]:
        trimmed = [c.strip() for c in v if c.strip()]
        if not trimmed:
            raise ValueError("companies must contain at least one non-empty name")
        if len(trimmed) > _MAX_COMPANIES:
            raise ValueError(
                f"companies list too long ({len(trimmed)}): max {_MAX_COMPANIES} per batch"
            )
        return trimmed


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior BD professional drafting batch cold outreach emails for a biotech BD workflow.

# Your task

Write one personalized outreach email for EACH company in the provided list. Each email must
be meaningfully different — not a find-replace of the company name. Where possible, vary:
- The lead sentence (reference a different pipeline gap, recent deal, or stated focus area)
- The emphasis (different aspects of the asset relevant to each company's profile)
- The specific ask (can vary: intro call, CDA, conference meeting)

# Hard rules (apply to EVERY email)

1. **Output format**: emit emails in order. Separate each email with exactly this delimiter on its own line:
   ===EMAIL:<CompanyName>===
   Then immediately the Subject: line, blank line, and body. No preamble, no commentary after the last email.

2. **Length**: 80–180 words per body. Cold outreach shorter, follow-ups can be longer.

3. **No clichés**: never "I hope this email finds you well", "circling back", "synergy", "leverage", "reach out".

4. **Specificity**: every claim references a concrete asset, indication, target, mechanism, or data point.

5. **One ask per email**: a single clear next step at the end.

6. **Subject line**: ≤ 9 words, references the asset or topic, never starts with "Re:" or "FYI:".

7. **No fake urgency**: don't fabricate competing interest or deadlines.

8. **Perspective**:
   - Seller → you own the asset and are pitching to a potential licensee/buyer
   - Buyer → you are interested in an asset they own

9. **Language flag**: en = English, zh = 中文 (keep scientific terms in English).

10. **Tone flag**: formal = neutral professional. warm = lighter structure, first-name where appropriate.

# Output structure (example for 2 companies)

===EMAIL:Pfizer===
Subject: KRAS G12D inhibitor Phase 2 data — 20-min call

Dear [Name],

[body...]

Best regards,
[Signature]

===EMAIL:Novartis===
Subject: ...

[body...]

Best regards,
[Signature]
"""


_PURPOSE_FRAGMENTS = {
    "cold_outreach": (
        "First touch — recipients have no prior context. Earn the reply: "
        "open with one specific reason this asset is relevant to EACH company. "
        "Ask for a 20-min intro call OR a CDA, not both."
    ),
    "meeting_request": (
        "Both sides are aligned to explore — you're scheduling working sessions. "
        "Propose 2 time-slot options, name attendees from your side, list 2-3 agenda items."
    ),
    "follow_up": (
        "Generic nudge after silence. ≤ 100 words each. Reference last touchpoint, "
        "offer one new data point, re-state the ask."
    ),
}

_PURPOSE_LABEL = {
    "cold_outreach": "Cold Outreach / First Touch",
    "meeting_request": "Meeting Request",
    "follow_up": "Generic Follow-up / Nudge",
}

USER_PROMPT_TEMPLATE = """## Batch email task

- **Purpose**: {purpose_label} — {purpose_blurb}
- **From perspective**: {perspective_blurb}
- **Today**: {today}

## Sender

- **Company**: {from_company}
- **Name**: {from_name}
- **Role**: {from_role}

## Asset / topic

{asset_block}

## Tone & language

- **Tone**: {tone}
- **Language**: {language}

## Additional shared context

{extra_block}

## Target companies (write one email per company, in this order)

{companies_block}

## Task

Write {n_companies} emails, one per company. Use the `===EMAIL:<CompanyName>===` delimiter.
Each email: Subject: line, blank line, body (80-180 words), sign-off, signature.
Vary the opening line and emphasis for each company. No commentary before or after.
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class BatchOutreachService(ReportService):
    slug = "batch-outreach"
    display_name = "Batch Outreach Email"
    description = (
        "给多家 MNC / 买方批量起草个性化 outreach 邮件（一次调用，最多 10 家）。"
        "从 /buyers 结果获取公司列表最常用，自动归档为 outreach pipeline 草稿记录。"
    )
    chat_tool_name = "batch_outreach_email"
    chat_tool_description = (
        "Draft personalized outreach emails to multiple companies in one call (max 10). "
        "Ideal after /buyers: pass the top-N company names and shared asset context. "
        "Each email is individually tailored, auto-logged to the outreach pipeline as "
        "'draft', and returned in a single markdown file with per-company sections. ~30-50s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "companies": {
                "type": "array",
                "items": {"type": "string"},
                "description": f"Company names to email (max {_MAX_COMPANIES}).",
            },
            "purpose": {
                "type": "string",
                "enum": ["cold_outreach", "meeting_request", "follow_up"],
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
            "tone": {"type": "string", "enum": ["formal", "warm"], "default": "formal"},
            "language": {"type": "string", "enum": ["en", "zh"], "default": "en"},
            "extra_context": {"type": "string"},
        },
        "required": ["companies"],
    }
    input_model = BatchOutreachInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 40
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = BatchOutreachInput(**params)
        today = datetime.date.today().isoformat()
        n = len(inp.companies)

        ctx.log(
            f"Drafting batch outreach to {n} companies: {', '.join(inp.companies[:5])}"
            + (" …" if n > 5 else "")
        )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            purpose_label=_PURPOSE_LABEL[inp.purpose],
            purpose_blurb=_PURPOSE_FRAGMENTS[inp.purpose],
            perspective_blurb=self._perspective_blurb(inp.from_perspective),
            today=today,
            from_company=inp.from_company or "(unspecified)",
            from_name=inp.from_name or "(unspecified)",
            from_role=inp.from_role or "(unspecified)",
            asset_block=inp.asset_context or "(no specific asset — generic relationship outreach)",
            tone=inp.tone,
            language=inp.language,
            extra_block=inp.extra_context or "(none)",
            companies_block="\n".join(f"{i + 1}. {c}" for i, c in enumerate(inp.companies)),
            n_companies=n,
        )

        raw = ctx.llm(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=min(900 * n, 7000),
        )

        if not raw or len(raw.strip()) < 100:
            raise RuntimeError("LLM produced an empty or too-short batch email output.")

        # Parse per-company sections
        sections = self._parse_sections(raw, inp.companies)

        ctx.log(f"Parsed {len(sections)} email sections")

        # Auto-log every drafted email to outreach_db (status=draft)
        logged_ids = self._auto_log_all(inp, sections, ctx)
        n_logged = sum(1 for v in logged_ids.values() if v is not None)
        if n_logged:
            ctx.log(f"Auto-logged {n_logged}/{len(sections)} drafts to outreach pipeline")

        # Compose output markdown
        markdown = self._compose_markdown(inp, sections, today)

        slug = safe_slug(f"batch_{inp.purpose}_{today}") or "batch_email"
        md_filename = f"{slug}.md"
        ctx.save_file(md_filename, markdown, format="md")

        suggested_commands = self._build_chips(inp)

        meta: dict = {
            "title": f"Batch {_PURPOSE_LABEL[inp.purpose]} → {n} companies",
            "companies": inp.companies,
            "purpose": inp.purpose,
            "from_perspective": inp.from_perspective,
            "n_emails": n,
            "n_logged": n_logged,
            "auto_logged_event_ids": {k: v for k, v in logged_ids.items() if v is not None},
            "suggested_commands": suggested_commands,
        }

        return ReportResult(markdown=markdown, meta=meta)

    # ── Parsing ─────────────────────────────────────────────

    def _parse_sections(self, raw: str, companies: list[str]) -> dict[str, str]:
        """Split LLM output by ===EMAIL:<Company>=== delimiters.

        Falls back to even-splitting if delimiters are absent (shouldn't happen
        with a well-behaved model, but we'd rather degrade than crash).
        """
        import re

        delimiter_pattern = re.compile(r"===EMAIL:(.+?)===\s*", re.IGNORECASE)
        parts = delimiter_pattern.split(raw)

        # parts layout after split: ['preamble', 'Company1', 'body1', 'Company2', 'body2', ...]
        sections: dict[str, str] = {}
        if len(parts) >= 3:
            # Odd indices are company names, even indices (≥2) are bodies
            for i in range(1, len(parts) - 1, 2):
                cname = parts[i].strip()
                body = parts[i + 1].strip() if i + 1 < len(parts) else ""
                if cname and body:
                    sections[cname] = body
        else:
            # Fallback: no delimiters found — assign whole output to first company
            logger.warning("BatchOutreach: no email delimiters found in LLM output; using fallback")
            sections[companies[0]] = raw.strip()

        # Ensure every requested company has a section (fill blank if missing)
        for c in companies:
            if c not in sections:
                # Try case-insensitive match
                match = next((k for k in sections if k.lower() == c.lower()), None)
                if match:
                    sections[c] = sections.pop(match)
                else:
                    sections[c] = "(LLM did not produce an email for this company)"

        return sections

    # ── Auto-log ────────────────────────────────────────────

    def _auto_log_all(
        self,
        inp: BatchOutreachInput,
        sections: dict[str, str],
        ctx: ReportContext,
    ) -> dict[str, int | None]:
        """Log every drafted email to outreach_db as status='draft'."""
        if not ctx.user_id:
            return {c: None for c in sections}

        results: dict[str, int | None] = {}
        for company, body in sections.items():
            subject = self._extract_subject(body)
            try:
                event_id = outreach_db.insert_event(
                    user_id=ctx.user_id,
                    to_company=company,
                    purpose=inp.purpose,
                    channel="email",
                    status="draft",
                    to_contact=None,
                    asset_context=inp.asset_context,
                    perspective=inp.from_perspective,
                    subject=subject,
                    notes="Auto-logged by /batch-outreach service",
                    session_id=None,
                )
                results[company] = event_id
            except Exception:
                logger.exception("Auto-log failed for batch email to %s", company)
                results[company] = None

        return results

    # ── Markdown composition ─────────────────────────────────

    def _compose_markdown(
        self, inp: BatchOutreachInput, sections: dict[str, str], today: str
    ) -> str:
        header = (
            f"<!-- BD Go Batch Outreach · generated {today}\n"
            f"     purpose: {inp.purpose} · perspective: {inp.from_perspective}"
            f" · lang: {inp.language} · tone: {inp.tone}\n"
            f"     companies: {', '.join(inp.companies)} -->\n\n"
        )
        header += f"# Batch Outreach — {_PURPOSE_LABEL[inp.purpose]}\n\n"
        header += (
            f"*Generated {today} · {len(sections)} emails · {inp.from_perspective} perspective*\n\n"
        )
        header += "---\n\n"

        parts: list[str] = [header]
        for i, (company, body) in enumerate(sections.items(), 1):
            section = f"## {i}. {company}\n\n{body.strip()}\n\n---\n\n"
            parts.append(section)

        return "".join(parts)

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _extract_subject(body: str) -> str | None:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("subject:"):
                return stripped[len("subject:") :].strip() or None
        return None

    def _perspective_blurb(self, perspective: str) -> str:
        if perspective == "seller":
            return "We are the SELLER — we own the asset and are pitching to potential buyers / licensees."
        return "We are the BUYER — we are interested in assets the recipients own."

    def _build_chips(self, inp: BatchOutreachInput) -> list[dict]:
        chips: list[dict] = [
            {
                "label": "View Outreach Pipeline",
                "command": "/outreach",
                "slug": "outreach-list",
            }
        ]
        # If cold outreach, suggest doing a meeting brief once one replies
        if inp.purpose == "cold_outreach":
            first = inp.companies[0] if inp.companies else ""
            chips.append(
                {
                    "label": "Pre-meeting Brief",
                    "command": (
                        f'/meeting counterparty="{first}" meeting_purpose=intro_pitch'
                        + (f' asset_context="{inp.asset_context}"' if inp.asset_context else "")
                    ),
                    "slug": "meeting-brief",
                }
            )
        return chips
