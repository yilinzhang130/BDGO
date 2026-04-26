"""ClinicalTrials.gov live search tool for the BDGO chat assistant.

Exposes ``search_clinicaltrials`` — gives the LLM access to live trial
data from ClinicalTrials.gov, complementing the static CRM 临床 table.

Use-cases:
  - Competitor landscape for a given drug class / target
  - Verifying a company's global pipeline phase and status
  - Checking enrollment, primary completion dates for timing analysis
  - Discovering trials our CRM doesn't yet have

Unlike ``search_clinical`` (which queries our in-house CRM), this tool
calls the real ClinicalTrials.gov API, so results are always current.
"""

from __future__ import annotations

from services.external.clinicaltrials import search_trials

# ───────────────────────��─────────────────────────���───────────
# Tool schema (LLM-facing)
# ─────────────────────────────────────────────────────────────

SCHEMAS = [
    {
        "name": "search_clinicaltrials",
        "description": (
            "Search ClinicalTrials.gov for active/completed clinical trials. "
            "Returns up to 30 real-time results with NCT ID, title, phase, status, "
            "sponsor, conditions, intervention names, enrollment, primary completion "
            "date, and a brief summary. "
            "Use this to: (1) check a drug's global trial landscape, "
            "(2) verify a company's clinical pipeline beyond our CRM, "
            "(3) find enrollment/timing data for outreach window analysis. "
            "At least one of query, condition, intervention, or sponsor is required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text search matching trial title/description (e.g. 'KRAS G12D NSCLC')"
                    ),
                },
                "condition": {
                    "type": "string",
                    "description": (
                        "Disease or condition to filter by "
                        "(e.g. 'Non-small cell lung cancer', 'NSCLC', 'AML')"
                    ),
                },
                "intervention": {
                    "type": "string",
                    "description": (
                        "Drug name or intervention to filter by "
                        "(e.g. 'sotorasib', 'adagrasib', 'PD-1 antibody')"
                    ),
                },
                "sponsor": {
                    "type": "string",
                    "description": (
                        "Sponsor / company name to filter by (e.g. 'Amgen', 'BeiGene', 'Zymeworks')"
                    ),
                },
                "phase": {
                    "type": "string",
                    "description": (
                        "Clinical phase filter: 'Phase 1', 'Phase 2', 'Phase 3', "
                        "'Phase 1/2', 'Phase 2/3'"
                    ),
                },
                "status": {
                    "type": "string",
                    "description": (
                        "Trial status filter: 'Recruiting', 'Active', 'Completed', "
                        "'Terminated', 'Not Yet Recruiting'"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (1–30, default 10)",
                    "default": 10,
                },
            },
        },
    }
]

# ─────────────────────────────────────────────────────────────
# Implementation
# ─────────────────────────────────────────────────────────────


def _search_clinicaltrials(
    query: str = "",
    condition: str = "",
    intervention: str = "",
    sponsor: str = "",
    phase: str = "",
    status: str = "",
    limit: int = 10,
    **_: object,
) -> dict:
    """Execute ClinicalTrials.gov search and return formatted results."""
    if not any([query, condition, intervention, sponsor]):
        return {
            "error": "At least one of query, condition, intervention, or sponsor is required",
            "trials": [],
            "total": 0,
        }

    trials = search_trials(
        query=query,
        condition=condition,
        intervention=intervention,
        sponsor=sponsor,
        phase=phase,
        status=status,
        limit=limit,
    )
    return {
        "trials": trials,
        "total": len(trials),
        "source": "ClinicalTrials.gov (live)",
        "note": (
            "Results from ClinicalTrials.gov API v2. For BDGO-CRM in-house trials, "
            "use search_clinical instead."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Registry exports
# ─────────────────────────────────────────────────────────────

IMPLS: dict = {"search_clinicaltrials": _search_clinicaltrials}

# No CRM table → no field stripping needed for this tool
TABLE_MAP: dict = {}
