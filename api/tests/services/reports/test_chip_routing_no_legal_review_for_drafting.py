"""Regression tests: no service that emits "Draft X" chips should route
to /legal review.

Background:
  /legal is review-mode — its input model requires contract_text or
  filename or source_task_id. When a service emits a chip labeled
  "Draft X" but routes to /legal contract_type=X, clicking it lands the
  user on a review flow with nothing to review (the document doesn't
  exist yet — they're trying to draft it). This is a closed-loop bug
  that bit /draft-X chips (#119), /log + /import-reply ts_signed +
  /email cold_outreach (#121), and /evaluate / /rnpv / /teaser /
  /dataroom (this fix).

These tests run against the actual chip output of each service to lock
the fix in place: any future regression that re-introduces a /legal
chip with a Draft-style label fails CI before shipping.
"""

from __future__ import annotations


def _has_review_chip_for_drafting_label(chips: list[dict]) -> bool:
    """A chip is suspect if its label says 'Draft' but slug is 'legal-review'."""
    for c in chips:
        label = c.get("label", "").lower()
        slug = c.get("slug", "")
        if "draft" in label and slug == "legal-review":
            return True
    return False


def _exec_code(py_path) -> str:
    """Read source and strip docstrings + comments so 'forbidden'
    substrings inside explanatory comments don't trigger the check.
    Only the live chip-emitting code matters."""
    import re

    with open(py_path, encoding="utf-8") as f:
        src = f.read()
    src = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
    src = re.sub(r"'''.*?'''", "", src, flags=re.DOTALL)
    src = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
    src = re.sub(r"(?<!:)\s+#[^\n]*", "", src)
    return src


def test_deal_evaluator_routes_ts_chip_to_draft_ts():
    from services.reports import deal_evaluator as mod

    code = _exec_code(mod.__file__)
    assert "/draft-ts" in code, "deal_evaluator must route TS chip to /draft-ts"
    assert "/legal contract_type=ts" not in code, (
        "deal_evaluator must NOT route TS chip to /legal review (broken closed loop)"
    )


def test_rnpv_routes_ts_chip_to_draft_ts():
    from services.reports import rnpv_valuation as mod

    code = _exec_code(mod.__file__)
    assert "/draft-ts" in code, "rnpv_valuation must route TS chip to /draft-ts"
    assert "/legal contract_type=ts" not in code, (
        "rnpv_valuation must NOT route TS chip to /legal review"
    )


def test_deal_teaser_routes_post_chip_to_email_not_legal_cda():
    from services.reports import deal_teaser as mod

    code = _exec_code(mod.__file__)
    assert "/legal contract_type=cda" not in code, (
        "deal_teaser must NOT route to /legal cda (broken closed loop)"
    )
    assert "/email" in code and "cold_outreach" in code, (
        "deal_teaser should route to /email cold_outreach (send teaser to buyer)"
    )


def test_data_room_does_not_emit_legal_cda_chip():
    """data_room previously emitted a "Draft CDA / NDA" chip routing to
    /legal contract_type=cda — broken closed loop (see #121 + this fix).
    The chip was removed entirely; the always-on /dd seller-prep chip
    remains."""
    from services.reports.data_room import DataRoomInput, DataRoomService

    svc = DataRoomService()
    for purpose in ("licensing", "partnership", "acquisition", "dd_response"):
        inp = DataRoomInput(
            company_name="Peg-Bio",
            asset_name="PEG-001",
            modality="small_molecule",
            phase="Phase 2",
            purpose=purpose,
        )
        chips = svc._build_suggested_commands(inp)
        assert not _has_review_chip_for_drafting_label(chips), (
            f"data_room with purpose={purpose} emitted a 'Draft X' chip "
            f"routing to /legal review: {chips}"
        )
        # /dd chip always present
        assert any(c["slug"] == "dd-checklist" for c in chips)
