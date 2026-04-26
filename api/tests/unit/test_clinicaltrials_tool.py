"""Unit tests for the ClinicalTrials.gov chat tool (P2-10).

Tests:
  1. Tool schema registration — name, input_schema, description present.
  2. _search_clinicaltrials impl: error guard when no filters given.
  3. search_trials: response parsing with a mock HTTP response.
  4. Phase / status mapping helpers.
  5. search_trials: empty/all-optional params protection.
  6. Tool module exports SCHEMAS, IMPLS, TABLE_MAP.
  7. Planner inventory includes search_clinicaltrials.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────
# Schema registration
# ─────────────────────────────────────────────────────────────


def test_tool_schema_registered():
    from routers.chat.tools import TOOLS

    names = [t["name"] for t in TOOLS]
    assert "search_clinicaltrials" in names


def test_tool_impl_registered():
    from routers.chat.tools import TOOL_IMPL

    assert "search_clinicaltrials" in TOOL_IMPL
    assert callable(TOOL_IMPL["search_clinicaltrials"])


def test_tool_schema_has_description():
    from routers.chat.tools import TOOLS

    schema = next(t for t in TOOLS if t["name"] == "search_clinicaltrials")
    assert schema.get("description")
    assert len(schema["description"]) > 20


def test_tool_schema_has_input_schema():
    from routers.chat.tools import TOOLS

    schema = next(t for t in TOOLS if t["name"] == "search_clinicaltrials")
    inp = schema.get("input_schema", {})
    props = inp.get("properties", {})
    for field in ("query", "condition", "intervention", "sponsor", "phase", "status", "limit"):
        assert field in props, f"Missing input field: {field}"


def test_tool_module_exports():
    from routers.chat.tools import clinicaltrials as ct_mod

    assert hasattr(ct_mod, "SCHEMAS")
    assert hasattr(ct_mod, "IMPLS")
    assert hasattr(ct_mod, "TABLE_MAP")
    assert isinstance(ct_mod.SCHEMAS, list)
    assert isinstance(ct_mod.IMPLS, dict)
    assert isinstance(ct_mod.TABLE_MAP, dict)
    assert ct_mod.TABLE_MAP == {}  # no CRM table — no field stripping


# ─────────────────────────────────────────────────────────────
# Implementation: error guard
# ─────────────────────────────────────────────────────────────


def test_no_filters_returns_error():
    from routers.chat.tools.clinicaltrials import _search_clinicaltrials

    result = _search_clinicaltrials()
    assert "error" in result
    assert result["trials"] == []
    assert result["total"] == 0


def test_no_filters_with_only_phase_returns_error():
    """Phase alone is not enough — need at least one text filter."""
    from routers.chat.tools.clinicaltrials import _search_clinicaltrials

    result = _search_clinicaltrials(phase="Phase 2")
    assert "error" in result


def test_no_filters_with_only_status_returns_error():
    from routers.chat.tools.clinicaltrials import _search_clinicaltrials

    result = _search_clinicaltrials(status="Recruiting")
    assert "error" in result


# ─────────────────────────────────────────────────────────────
# search_trials — HTTP mock
# ─────────────────────────────────────────────────────────────

_MOCK_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT12345678",
            "briefTitle": "Phase 2 Study of DrugX in NSCLC",
        },
        "statusModule": {
            "overallStatus": "RECRUITING",
            "startDateStruct": {"date": "2024-03"},
            "primaryCompletionDateStruct": {"date": "2026-06"},
        },
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE2"],
            "enrollmentInfo": {"count": 120},
        },
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme Bio"}},
        "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer"]},
        "armsInterventionsModule": {"interventions": [{"name": "DrugX", "type": "DRUG"}]},
        "descriptionModule": {"briefSummary": "A Phase 2 trial of DrugX in NSCLC patients."},
        "outcomesModule": {
            "primaryOutcomes": [{"measure": "Overall Response Rate"}, {"measure": "PFS"}]
        },
    }
}

_MOCK_RESPONSE_JSON = {"studies": [_MOCK_STUDY], "totalCount": 1}


def _fake_get(url, params, timeout):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = _MOCK_RESPONSE_JSON
    return resp


def test_search_trials_happy_path():
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        results = search_trials(condition="NSCLC")

    assert len(results) == 1
    trial = results[0]
    assert trial["nct_id"] == "NCT12345678"
    assert trial["status"] == "Recruiting"
    assert trial["phase"] == "Phase 2"
    assert trial["sponsor"] == "Acme Bio"
    assert "Non-Small Cell Lung Cancer" in trial["conditions"]
    assert "DrugX (DRUG)" in trial["interventions"]
    assert trial["enrollment"] == 120
    assert "Overall Response Rate" in trial["primary_outcomes"]
    assert trial["url"] == "https://clinicaltrials.gov/study/NCT12345678"


def test_search_trials_returns_empty_on_http_error():
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = Exception("Network error")
        results = search_trials(condition="NSCLC")

    assert results == []


def test_search_trials_returns_empty_for_no_filters():
    """Blank call — no API hit, returns [] guard in client."""
    from services.external.clinicaltrials import search_trials

    results = search_trials()
    assert results == []


def test_search_trials_limit_clamped():
    """limit > 30 is clamped to 30; limit < 1 is clamped to 1."""
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="AML", limit=999)
        call_params = mock_client.get.call_args[1]["params"]
        assert call_params["pageSize"] == 30

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="AML", limit=0)
        call_params = mock_client.get.call_args[1]["params"]
        assert call_params["pageSize"] == 1


# ─────────────────────────────────────────────────────────────
# Phase / status mapping
# ─────────────────────────────────────────────────────────────


def test_phase_mapping_phase2():
    """Phase 2 query parameter is mapped to PHASE2 enum."""
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="CRC", phase="Phase 2")
        params = mock_client.get.call_args[1]["params"]
        assert params.get("filter.phase") == "PHASE2"


def test_phase_mapping_phase1_2():
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="CRC", phase="Phase 1/2")
        params = mock_client.get.call_args[1]["params"]
        assert params.get("filter.phase") == "PHASE1_PHASE2"


def test_unknown_phase_not_sent():
    """Unrecognized phase strings should not add a filter.phase param."""
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="CRC", phase="Open Label Extension")
        params = mock_client.get.call_args[1]["params"]
        assert "filter.phase" not in params


def test_status_mapping_recruiting():
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="CRC", status="Recruiting")
        params = mock_client.get.call_args[1]["params"]
        assert params.get("filter.overallStatus") == "RECRUITING"


def test_status_mapping_active():
    from services.external.clinicaltrials import search_trials

    with patch("services.external.clinicaltrials._http_client") as mock_client:
        mock_client.get.side_effect = _fake_get
        search_trials(condition="CRC", status="Active")
        params = mock_client.get.call_args[1]["params"]
        assert params.get("filter.overallStatus") == "ACTIVE_NOT_RECRUITING"


# ─────────────────────────────────────────────────────────────
# Planner inventory sync
# ─────────────────────────────────────────────────────────────


def test_planner_prompt_includes_search_clinicaltrials():
    """Planner system prompt must mention search_clinicaltrials so the LLM
    knows the tool exists. A drift would silently degrade IP/landscape plans."""
    from planner import PLANNER_SYSTEM_PROMPT

    assert "search_clinicaltrials" in PLANNER_SYSTEM_PROMPT, (
        "search_clinicaltrials is registered as a chat tool but missing from "
        "PLANNER_SYSTEM_PROMPT. Add it to the tool inventory section."
    )
