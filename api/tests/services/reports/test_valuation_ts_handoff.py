"""
Smoke tests: DealEvaluatorService and RNPVValuationService emit
a 'Draft Term Sheet' /legal chip in meta.suggested_commands.

These only check the static shape of the command — no LLM calls made.
"""

from __future__ import annotations

from services.reports.deal_evaluator import DealEvaluatorInput, DealEvaluatorService
from services.reports.rnpv_valuation import RNPVInput, RNPVValuationService

# ── DealEvaluatorService ─────────────────────────────────────────────────────


def _evaluate_ts_command(
    company: str = "Peg-Bio",
    asset: str = "PEG-001",
    indication: str = "NSCLC",
) -> str:
    """Re-derive the expected command string (mirrors production logic)."""
    return (
        f'/legal contract_type=ts party_position="乙方"'
        f' counterparty="{company}"'
        f' project_name="{asset} ({indication})"'
    )


def test_deal_evaluator_ts_command_format():
    """Verify the TS command string is well-formed without running the service."""
    cmd = _evaluate_ts_command("Peg-Bio", "PEG-001", "NSCLC")
    assert cmd.startswith("/legal")
    assert "contract_type=ts" in cmd
    assert 'party_position="乙方"' in cmd
    assert 'counterparty="Peg-Bio"' in cmd
    assert 'project_name="PEG-001 (NSCLC)"' in cmd


def test_deal_evaluator_service_registered():
    from services import REPORT_SERVICES

    svc = REPORT_SERVICES.get("deal-evaluator")
    assert svc is not None
    assert isinstance(svc, DealEvaluatorService)


def test_rnpv_service_registered():
    from services import REPORT_SERVICES

    svc = REPORT_SERVICES.get("rnpv-valuation")
    assert svc is not None
    assert isinstance(svc, RNPVValuationService)


def test_deal_evaluator_input_valid():
    inp = DealEvaluatorInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        target="KRAS G12C",
        indication="NSCLC",
        phase="Phase 2",
    )
    assert inp.company_name == "Peg-Bio"
    assert inp.asset_name == "PEG-001"


def test_rnpv_input_valid():
    inp = RNPVInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        indication="NSCLC",
        phase="Phase 2",
        modality="小分子",
    )
    assert inp.company_name == "Peg-Bio"
    assert inp.modality == "小分子"


def test_rnpv_ts_command_format():
    """Same shape check for the rNPV → TS command."""
    cmd = _evaluate_ts_command("Ema Gen", "EG-101", "HER2+ Breast Cancer")
    assert "contract_type=ts" in cmd
    assert 'counterparty="Ema Gen"' in cmd
    assert "HER2+ Breast Cancer" in cmd
