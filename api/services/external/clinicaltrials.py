"""ClinicalTrials.gov API v2 client.

Provides live trial search beyond the static CRM 临床 table.
The ClinicalTrials.gov API is free, no API key required.
Rate limit: 10 req/s (we stay well under with 0.2s spacing).

API reference: https://clinicaltrials.gov/data-api/api

Typical use-cases in BD:
  - Find all active trials for a drug/target (competitor landscape)
  - Check a company's global pipeline not yet in our CRM
  - Verify phase and status before writing a report
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
_RATE_LIMIT_SECONDS = 0.2  # 5 req/s with margin
_DEFAULT_TIMEOUT = 15.0

# Shared client — ClinicalTrials.gov supports keep-alive.
_http_client = httpx.Client(
    limits=httpx.Limits(max_keepalive_connections=3, max_connections=5),
)

import atexit

atexit.register(_http_client.close)

# ClinicalTrials.gov v2 field list we always request.
# Keeps payload size small vs. fetching all fields.
_FIELDS = ",".join(
    [
        "NCTId",
        "BriefTitle",
        "OfficialTitle",
        "OverallStatus",
        "Phase",
        "Condition",
        "InterventionName",
        "InterventionType",
        "LeadSponsorName",
        "StartDate",
        "PrimaryCompletionDate",
        "StudyFirstPostDate",
        "EnrollmentCount",
        "PrimaryOutcomeMeasure",
        "BriefSummary",
        "StudyType",
    ]
)

# Human-readable phase mapping
_PHASE_MAP = {
    "PHASE1": "Phase 1",
    "PHASE1_PHASE2": "Phase 1/2",
    "PHASE2": "Phase 2",
    "PHASE2_PHASE3": "Phase 2/3",
    "PHASE3": "Phase 3",
    "PHASE4": "Phase 4",
    "NA": "N/A",
    "EARLY_PHASE1": "Early Phase 1",
}

# Human-readable status mapping
_STATUS_MAP = {
    "RECRUITING": "Recruiting",
    "NOT_YET_RECRUITING": "Not Yet Recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
    "COMPLETED": "Completed",
    "SUSPENDED": "Suspended",
    "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "UNKNOWN": "Unknown",
}


def _coerce_list(v: Any) -> list:
    if isinstance(v, list):
        return v
    if v is None:
        return []
    return [v]


def _parse_study(study: dict) -> dict:
    """Flatten one ClinicalTrials.gov v2 study record into a compact dict."""
    ps = study.get("protocolSection", {})
    id_module = ps.get("identificationModule", {})
    status_module = ps.get("statusModule", {})
    design_module = ps.get("designModule", {})
    sponsor_module = ps.get("sponsorCollaboratorsModule", {})
    cond_module = ps.get("conditionsModule", {})
    intervention_module = ps.get("armsInterventionsModule", {})
    desc_module = ps.get("descriptionModule", {})
    outcomes_module = ps.get("outcomesModule", {})
    enroll_module = design_module.get("enrollmentInfo", {})

    # Phase: API returns list like ["PHASE2"] or ["PHASE1", "PHASE2"]
    phases_raw = design_module.get("phases", [])
    if isinstance(phases_raw, list) and phases_raw:
        phase = _PHASE_MAP.get(phases_raw[-1], phases_raw[-1])
    else:
        phase = ""

    # Status
    status_raw = status_module.get("overallStatus", "")
    status = _STATUS_MAP.get(status_raw, status_raw)

    # Conditions
    conditions = _coerce_list(cond_module.get("conditions", []))

    # Interventions — drug names
    interventions = []
    for arm in _coerce_list(intervention_module.get("interventions", [])):
        name = arm.get("name", "")
        itype = arm.get("type", "")
        if name:
            interventions.append(f"{name} ({itype})" if itype else name)

    # Sponsor
    sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")

    # Primary outcomes (first 2 only — keeps token count manageable)
    outcomes = []
    for o in _coerce_list(outcomes_module.get("primaryOutcomes", []))[:2]:
        m = o.get("measure", "")
        if m:
            outcomes.append(m)

    # Summary — trim to 400 chars for LLM frugality
    brief_summary = desc_module.get("briefSummary", "")
    if len(brief_summary) > 400:
        brief_summary = brief_summary[:397] + "..."

    # Enrollment
    try:
        enrollment = int(enroll_module.get("count", 0))
    except (ValueError, TypeError):
        enrollment = 0

    return {
        "nct_id": id_module.get("nctId", ""),
        "title": id_module.get("briefTitle", ""),
        "status": status,
        "phase": phase,
        "study_type": design_module.get("studyType", ""),
        "conditions": conditions[:5],  # cap
        "interventions": interventions[:5],
        "sponsor": sponsor,
        "start_date": status_module.get("startDateStruct", {}).get("date", ""),
        "primary_completion_date": status_module.get("primaryCompletionDateStruct", {}).get(
            "date", ""
        ),
        "enrollment": enrollment,
        "primary_outcomes": outcomes,
        "brief_summary": brief_summary,
        "url": f"https://clinicaltrials.gov/study/{id_module.get('nctId', '')}",
    }


def search_trials(
    query: str = "",
    condition: str = "",
    intervention: str = "",
    sponsor: str = "",
    phase: str = "",
    status: str = "",
    limit: int = 10,
) -> list[dict]:
    """Search ClinicalTrials.gov and return compact trial dicts.

    Args:
        query: free-text search (maps to query.term; matches title/description)
        condition: disease or condition (e.g. "NSCLC", "KRAS")
        intervention: drug name or intervention (e.g. "adagrasib", "PD-1")
        sponsor: company / sponsor name
        phase: "Phase 1" | "Phase 2" | "Phase 3" | "Phase 1/2" (loose match)
        status: "Recruiting" | "Completed" | "Active" | "Terminated" (loose match)
        limit: max results (1–30)

    Returns:
        List of compact study dicts. Empty list on error.
    """
    limit = max(1, min(limit, 30))

    # Build API params
    params: dict[str, Any] = {
        "pageSize": limit,
        "fields": _FIELDS,
        "format": "json",
    }
    if query:
        params["query.term"] = query
    if condition:
        params["query.cond"] = condition
    if intervention:
        params["query.intr"] = intervention
    if sponsor:
        params["query.spons"] = sponsor

    # Phase filter — map human-readable to API enum
    if phase:
        phase_upper = phase.upper().replace(" ", "").replace("/", "_")
        # Common aliases
        _ALIAS = {
            "PHASE1": "PHASE1",
            "PHASE2": "PHASE2",
            "PHASE3": "PHASE3",
            "PHASE4": "PHASE4",
            # Phase 1/2 — slash normalised to _ by replace above
            "PHASE1_2": "PHASE1_PHASE2",
            "PHASE1/2": "PHASE1_PHASE2",
            "PHASE12": "PHASE1_PHASE2",
            # Phase 2/3
            "PHASE2_3": "PHASE2_PHASE3",
            "PHASE2/3": "PHASE2_PHASE3",
            "PHASE23": "PHASE2_PHASE3",
        }
        mapped_phase = _ALIAS.get(phase_upper, "")
        if mapped_phase:
            params["filter.phase"] = mapped_phase

    # Status filter — map human label to API enum
    if status:
        status_upper = status.upper().replace(" ", "_").replace(",", "")
        _STATUS_ALIAS = {
            "RECRUITING": "RECRUITING",
            "ACTIVE": "ACTIVE_NOT_RECRUITING",
            "ACTIVE_NOT_RECRUITING": "ACTIVE_NOT_RECRUITING",
            "COMPLETED": "COMPLETED",
            "NOT_YET_RECRUITING": "NOT_YET_RECRUITING",
            "TERMINATED": "TERMINATED",
            "SUSPENDED": "SUSPENDED",
            "WITHDRAWN": "WITHDRAWN",
        }
        mapped_status = _STATUS_ALIAS.get(status_upper, "")
        if mapped_status:
            params["filter.overallStatus"] = mapped_status

    if not any([query, condition, intervention, sponsor]):
        # Refuse blank search — would return 30 random trials
        return []

    try:
        resp = _http_client.get(_BASE_URL, params=params, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("ClinicalTrials.gov search error: %s", e)
        return []
    finally:
        time.sleep(_RATE_LIMIT_SECONDS)

    studies = data.get("studies", [])
    return [_parse_study(s) for s in studies]
