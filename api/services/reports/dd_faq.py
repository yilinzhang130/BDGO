"""
DD FAQ Generator — pre-generate buyer due-diligence questions + our answers.

S3-04: Before any meaningful BD meeting or data room session, the sell-side
team needs to anticipate what the buyer will ask. "Getting surprised in the
data room" is a recurring complaint. This service generates a structured
Q&A document:

  - 12 buy-side DD questions, ranked by expected probability of being asked
  - For each question: our prepared answer, the data source that backs it,
    and a RAG-light flag for gaps (where we don't yet have an answer)
  - Grouped into 6 categories: Science/MOA, Clinical data, IP/competitive,
    Commercial/market, Manufacturing/CMC, Deal/financial
  - Optional perspective flip: can also prep seller-side answers to internal
    prep questions for the same meeting

Output: one markdown file (~800-1200 words), no .docx.
Design parallels MeetingBriefService but is answer-forward (not discussion-
topic forward) and goes deeper on data/evidence requirements.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

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

_MEETING_STAGES = (
    "intro_pitch",
    "cda_post_sign",
    "data_room",
    "term_sheet",
    "partnership",
    "regulatory_review",
)

_STAGE_LABEL = {
    "intro_pitch": "First BD Pitch / Intro Meeting",
    "cda_post_sign": "Post-CDA Discussion / Interest Confirmation",
    "data_room": "Data Room / Scientific Deep Dive",
    "term_sheet": "Term Sheet Negotiation",
    "partnership": "Co-development / Co-promotion Discussion",
    "regulatory_review": "Regulatory / CMC Review Meeting",
}

_STAGE_DEPTH = {
    "intro_pitch": (
        "This is a first-touch meeting. Questions will be high-level: "
        "asset overview, target rationale, differentiation vs. SoC, "
        "key data readouts, IP status, rough deal structure ask."
    ),
    "cda_post_sign": (
        "CDA just signed, buyer is doing initial diligence. Questions will probe "
        "the scientific story more deeply: MOA evidence, biomarker strategy, "
        "competitive positioning, preliminary safety, and manufacturing readiness."
    ),
    "data_room": (
        "Full scientific and commercial diligence. Questions will be very detailed: "
        "CSR summary, PK/PD, CMC, IP claim mapping, patent term, market model "
        "assumptions, regulatory strategy, key opinion leader relationships."
    ),
    "term_sheet": (
        "Both sides are interested and moving toward a deal. Questions will focus on "
        "deal structure, valuation assumptions, milestone triggers, royalty tiers, "
        "territory rights, co-promotion options, change-of-control provisions."
    ),
    "partnership": (
        "Exploring a co-development or co-promotion arrangement. Questions will focus on "
        "contribution split, governance (JSC), IP ownership of jointly developed assets, "
        "cost sharing, exit rights, and territory allocation."
    ),
    "regulatory_review": (
        "Review of regulatory dossier or CMC package. Questions will focus on "
        "IND/CTA filing status, safety database size, GMP compliance, "
        "manufacturing scale-up risks, RMP strategy, label negotiations."
    ),
}


class DDFaqInput(BaseModel):
    asset_context: str = Field(
        ...,
        description=(
            "Asset name + brief: modality, target, indication, phase, key data. "
            "E.g. 'KRAS G12D covalent inhibitor, NSCLC 2L, Phase 2, ORR 42%'"
        ),
    )
    meeting_stage: Literal[
        "intro_pitch",
        "cda_post_sign",
        "data_room",
        "term_sheet",
        "partnership",
        "regulatory_review",
    ] = "data_room"
    counterparty: str | None = Field(
        None,
        description="Buyer / partner name. Helps tailor questions to their known focus areas.",
    )
    our_perspective: Literal["seller", "buyer"] = "seller"
    known_gaps: str | None = Field(
        None,
        description=(
            "Known data gaps or weak points. E.g. 'no OS data yet', 'CMC scale-up not done'. "
            "These get flagged in the FAQ with 'GAP' status."
        ),
    )
    n_questions: int = Field(
        default=12,
        ge=5,
        le=20,
        description="Number of Q&A pairs to generate (5-20, default 12).",
    )
    include_web_search: bool = Field(
        default=True,
        description="Search for recent news about the counterparty to personalize questions.",
    )
    extra_context: str | None = Field(
        None,
        description="Any other context: prior meetings, known deal terms, specific concerns.",
    )

    @model_validator(mode="after")
    def _validate(self) -> DDFaqInput:
        if not self.asset_context.strip():
            raise ValueError("asset_context must not be empty")
        return self


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a veteran biotech BD professional preparing a sell-side team for a buyer due diligence session.

Your job: generate a structured Q&A document anticipating the questions a sophisticated buy-side team will ask about this asset.

# Output format (strict markdown)

## DD FAQ — {asset_name}
*Meeting stage: {stage_label} | Perspective: {perspective} | {n_questions} questions | {date}*

---

### Category: [Science / MOA]

**Q1. [Question text]**

> **Our answer:** [1-3 sentence prepared answer, specific data cited]
>
> **Data source:** [CSR / IND / publication / analyst report / etc.]
>
> **Status:** ✅ Ready / ⚠️ Partial / ❌ Gap

---

[repeat for each question; group by category]

---

## Preparation checklist

[5-7 bullet action items: data packages to pull, slides to update, people to brief]

---

# Question categories and target counts

Adjust counts based on meeting stage, but aim for approximately:
- **Science / MOA**: 3 questions (mechanism, target validation, biomarker)
- **Clinical data**: 3 questions (efficacy, safety, patient selection)
- **IP / Competitive**: 2 questions (patent term, FTO, competitor comparison)
- **Commercial / Market**: 2 questions (market size, pricing, reimbursement)
- **Manufacturing / CMC**: 1 question (scale-up, supply chain readiness)
- **Deal / Financial**: 1 question (deal structure ask, comparable deals)

At `intro_pitch` stage, lean toward Science/Clinical and skip deep CMC and Deal.
At `data_room` stage, cover all 6 categories with equal depth.
At `term_sheet` stage, emphasize Deal/Financial and IP/Competitive.

# Answer quality rules

1. **Every answer must cite a specific data point** — ORR%, PFS median, patent number, market size figure, comparable deal value. No vague statements.
2. **GAP detection**: if a question touches a known data gap (provided in context), mark Status as ❌ Gap and in the answer say what data we're working to generate + expected timeline.
3. **Partial answers**: if we have some data but it's incomplete (e.g. interim readout), mark Status as ⚠️ Partial.
4. **Buyer-specific angle**: if counterparty information is provided, tailor 2-3 questions to their known pipeline, deal history, or stated therapeutic focus.
5. **Honest framing**: do not spin. If a question is tough (e.g. "Why did your Phase 1 show Grade 3 DLTs?"), give a candid prepared answer that acknowledges the finding and contextualizes it.
6. **Actionable checklist**: the prep checklist at the end must be concrete actions, not platitudes. Examples: "Pull CSR summary from clinical team by Day -3", "Update CMC one-pager with batch 3 data", "Brief CMO on PD-L1 expression analysis."
"""

USER_PROMPT_TEMPLATE = """## Asset

{asset_context}

## Meeting

- **Stage**: {stage_label} — {stage_depth}
- **Perspective**: {perspective}
- **Counterparty**: {counterparty}
- **Today**: {today}

## Known data gaps / weak points

{gaps_block}

## Additional context

{extra_block}

## Counterparty intelligence (web search)

{web_block}

## Task

Generate {n_questions} Q&A pairs anticipating what the buy-side team will ask.
Group by category. For each: write the question, a specific prepared answer, the data source, and a Ready/Partial/Gap status.
End with a 5-7 item preparation checklist.
"""


# ─────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────


class DDFaqService(ReportService):
    slug = "dd-faq"
    display_name = "DD FAQ Generator"
    description = (
        "预生成买方 DD 问题 + 我方预备答案（5-20 题，按会议阶段裁剪）。"
        "覆盖 Science / Clinical / IP / Commercial / CMC / Deal 6 类，"
        "自动标记数据缺口（❌ Gap），输出备战 Checklist。"
    )
    chat_tool_name = "generate_dd_faq"
    chat_tool_description = (
        "Pre-generate buy-side due diligence questions + our prepared answers for a BD meeting. "
        "Tailored by meeting stage (intro pitch → data room → term sheet) and counterparty. "
        "Covers 6 categories: Science/MOA, Clinical, IP/Competitive, Commercial, CMC, Deal. "
        "Flags known data gaps. Returns markdown with Q&A + prep checklist. ~25-35s."
    )
    chat_tool_input_schema = {
        "type": "object",
        "properties": {
            "asset_context": {
                "type": "string",
                "description": (
                    "Asset name + brief: modality, target, indication, phase, key data. "
                    "E.g. 'KRAS G12D covalent inhibitor, NSCLC 2L, Phase 2, ORR 42%'"
                ),
            },
            "meeting_stage": {
                "type": "string",
                "enum": list(_MEETING_STAGES),
                "default": "data_room",
                "description": "Meeting stage determines question depth and category mix.",
            },
            "counterparty": {
                "type": "string",
                "description": "Buyer / partner name (optional, improves personalization).",
            },
            "our_perspective": {
                "type": "string",
                "enum": ["seller", "buyer"],
                "default": "seller",
            },
            "known_gaps": {
                "type": "string",
                "description": "Known data gaps or weak points to flag in answers.",
            },
            "n_questions": {
                "type": "integer",
                "minimum": 5,
                "maximum": 20,
                "default": 12,
            },
            "include_web_search": {
                "type": "boolean",
                "default": True,
            },
            "extra_context": {"type": "string"},
        },
        "required": ["asset_context"],
    }
    input_model = DDFaqInput
    mode = "async"
    output_formats = ["md"]
    estimated_seconds = 30
    category = "report"
    field_rules: dict = {}

    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        inp = DDFaqInput(**params)
        today = datetime.date.today().isoformat()
        stage_label = _STAGE_LABEL[inp.meeting_stage]

        ctx.log(
            f"Generating DD FAQ for {inp.asset_context[:60]}… "
            f"(stage={inp.meeting_stage}, n={inp.n_questions})"
        )

        # Optional web search for counterparty intelligence
        web_block = "(no web search)"
        if inp.include_web_search and inp.counterparty:
            web_block = self._query_web(inp, ctx)

        # Extract short asset name for the title
        asset_name = inp.asset_context.split(",")[0].strip()

        user_prompt = USER_PROMPT_TEMPLATE.format(
            asset_context=inp.asset_context,
            stage_label=stage_label,
            stage_depth=_STAGE_DEPTH[inp.meeting_stage],
            perspective=inp.our_perspective,
            counterparty=inp.counterparty or "(not specified)",
            today=today,
            gaps_block=inp.known_gaps or "(none provided)",
            extra_block=inp.extra_context or "(none)",
            web_block=web_block,
            n_questions=inp.n_questions,
        )

        system = SYSTEM_PROMPT.format(
            asset_name=asset_name,
            stage_label=stage_label,
            perspective=inp.our_perspective,
            n_questions=inp.n_questions,
            date=today,
        )

        markdown = ctx.llm(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=min(200 * inp.n_questions + 500, 5000),
        )

        if not markdown or len(markdown.strip()) < 200:
            raise RuntimeError("LLM produced an empty or too-short FAQ output.")

        slug_str = safe_slug(f"faq_{inp.meeting_stage}_{asset_name}") or "dd_faq"
        md_filename = f"{slug_str}_{today}.md"
        ctx.save_file(md_filename, markdown, format="md")
        ctx.log(f"DD FAQ saved ({inp.n_questions} questions, stage={inp.meeting_stage})")

        suggested_commands = self._build_chips(inp)

        meta: dict = {
            "title": f"DD FAQ — {asset_name} ({stage_label})",
            "asset_context": inp.asset_context,
            "meeting_stage": inp.meeting_stage,
            "counterparty": inp.counterparty,
            "n_questions": inp.n_questions,
            "our_perspective": inp.our_perspective,
            "suggested_commands": suggested_commands,
        }

        return ReportResult(markdown=markdown, meta=meta)

    # ── Helpers ─────────────────────────────────────────────

    def _query_web(self, inp: DDFaqInput, ctx: ReportContext) -> str:
        """2-3 Tavily queries for counterparty intelligence."""
        if not inp.counterparty:
            return "(no counterparty specified)"

        queries = [
            f"{inp.counterparty} oncology pipeline 2025 2026",
            f"{inp.counterparty} BD licensing deals recent",
        ]
        all_results: list[str] = []
        for q in queries:
            try:
                results = search(q, max_results=3)
                if results:
                    all_results.append(format_web_results(results, query=q))
            except Exception:
                logger.warning("Web search failed for query: %s", q)

        return "\n\n".join(all_results) if all_results else "(web search returned no results)"

    def _build_chips(self, inp: DDFaqInput) -> list[dict]:
        chips: list[dict] = []

        # Always offer to run a full DD checklist for follow-through
        dd_cmd = "/dd"
        if inp.counterparty:
            dd_cmd += f' company="{inp.counterparty}"'
        if inp.our_perspective:
            dd_cmd += f" perspective={inp.our_perspective}"
        chips.append(
            {
                "label": "Full DD Checklist",
                "command": dd_cmd,
                "slug": "dd-checklist",
            }
        )

        # Stage-specific forward chips
        if inp.meeting_stage == "intro_pitch":
            chips.append(
                {
                    "label": "Meeting Brief",
                    "command": (
                        f'/meeting counterparty="{inp.counterparty or ""}" '
                        f"meeting_purpose=intro_pitch"
                        + (f' asset_context="{inp.asset_context}"' if inp.asset_context else "")
                    ),
                    "slug": "meeting-brief",
                }
            )
        elif inp.meeting_stage == "term_sheet":
            chips.append(
                {
                    "label": "Draft Term Sheet",
                    "command": "/draft-ts",
                    "slug": "draft-ts",
                }
            )
        elif inp.meeting_stage == "data_room":
            chips.append(
                {
                    "label": "Data Room Checklist",
                    "command": (
                        "/dataroom" + (f' asset="{inp.asset_context}"' if inp.asset_context else "")
                    ),
                    "slug": "data-room",
                }
            )

        return chips
