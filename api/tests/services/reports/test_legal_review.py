"""
Unit tests for LegalReviewService input + helper logic.

These don't make LLM calls — that's integration territory. We exercise:
  - Input validation (text or filename required)
  - Per-type checklist coverage (all 6 types)
  - Title composition
  - Truncation
  - Service registration in REPORT_SERVICES
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.legal_review import (
    _CONTRACT_TYPE_NAMES,
    _MAX_CONTRACT_CHARS,
    _TYPE_CHECKLISTS,
    LegalReviewInput,
    LegalReviewService,
)


def test_service_registered():
    assert "legal-review" in REPORT_SERVICES
    svc = REPORT_SERVICES["legal-review"]
    assert isinstance(svc, LegalReviewService)
    assert svc.slug == "legal-review"
    assert "docx" in svc.output_formats and "md" in svc.output_formats


def test_input_requires_text_or_filename():
    with pytest.raises(ValueError, match="contract_text"):
        LegalReviewInput(contract_type="cda", party_position="甲方")


def test_input_accepts_text():
    inp = LegalReviewInput(
        contract_type="cda",
        party_position="甲方",
        contract_text="Confidential Information means...",
    )
    assert inp.contract_text.startswith("Confidential")


def test_input_accepts_filename():
    inp = LegalReviewInput(
        contract_type="mta",
        party_position="乙方",
        filename="emaygene_lilly_mta.pdf",
    )
    assert inp.filename == "emaygene_lilly_mta.pdf"


def test_all_contract_types_have_checklists():
    """Every value in the Literal must have a matching checklist + name."""
    expected = {"cda", "ts", "mta", "license", "co_dev", "spa"}
    assert set(_TYPE_CHECKLISTS.keys()) == expected
    assert set(_CONTRACT_TYPE_NAMES.keys()) == expected


def test_invalid_contract_type_rejected():
    with pytest.raises(ValueError):
        LegalReviewInput(
            contract_type="amendment",  # type: ignore[arg-type]
            party_position="甲方",
            contract_text="...",
        )


def test_invalid_party_position_rejected():
    with pytest.raises(ValueError):
        LegalReviewInput(
            contract_type="cda",
            party_position="第三方",  # type: ignore[arg-type]
            contract_text="...",
        )


def test_compose_title_with_full_context():
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="license",
        party_position="甲方",
        contract_text="x",
        counterparty="Eli Lilly",
        project_name="Project Aurora",
    )
    title = svc._compose_title(inp, _CONTRACT_TYPE_NAMES["license"])
    assert "Eli Lilly" in title
    assert "Project Aurora" in title
    assert "License Agreement" in title
    assert "审查意见" in title


def test_compose_title_minimal():
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="cda",
        party_position="乙方",
        contract_text="x",
    )
    title = svc._compose_title(inp, _CONTRACT_TYPE_NAMES["cda"])
    assert "审查意见" in title


def test_truncate_passthrough_under_limit():
    svc = LegalReviewService()
    text = "x" * 1000
    out, truncated = svc._truncate(text)
    assert out == text
    assert truncated is False


def test_truncate_caps_oversized_input():
    svc = LegalReviewService()
    text = "x" * (_MAX_CONTRACT_CHARS + 5000)
    out, truncated = svc._truncate(text)
    assert len(out) == _MAX_CONTRACT_CHARS
    assert truncated is True


def test_suggested_commands_cda_with_counterparty():
    """Stage 4 of BD lifecycle: CDA + known counterparty → offer /dd."""
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="cda",
        party_position="乙方",
        contract_text="x",
        counterparty="Eli Lilly",
    )
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 1
    assert sc[0]["slug"] == "dd-checklist"
    assert 'company="Eli Lilly"' in sc[0]["command"]
    assert sc[0]["command"].startswith("/dd")


def test_suggested_commands_cda_without_counterparty():
    """No counterparty → no useful /dd suggestion (DD needs a company)."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="cda", party_position="乙方", contract_text="x")
    assert svc._build_suggested_commands(inp) == []


def test_suggested_commands_end_of_lifecycle_silent():
    """license / co_dev / spa are end-of-lifecycle — no further chip."""
    svc = LegalReviewService()
    for ct in ("license", "co_dev", "spa"):
        inp = LegalReviewInput(
            contract_type=ct,
            party_position="甲方",
            contract_text="x",
            counterparty="Foo Pharma",
        )
        assert svc._build_suggested_commands(inp) == [], f"{ct} should not suggest"


def test_suggested_commands_mta_routes_to_draft_license():
    """MTA review → /draft-license (NOT /legal contract_type=license review).

    Previously fired /legal review which is broken: the License Agreement
    doesn't exist yet — that's exactly what this chip is supposed to
    initiate. Fixed alongside same closed-loop bug in /log /import-reply
    /evaluate /rnpv (#119, #121, #122). Audit added in this PR catches
    future regressions.
    """
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="mta",
        party_position="乙方",  # we're the provider in MTA → licensor in License
        contract_text="x",
        counterparty="Eli Lilly",
        project_name="PEG-001 (NSCLC)",
    )
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 1
    assert sc[0]["slug"] == "draft-license"
    assert sc[0]["label"] == "Draft License Agreement"
    cmd = sc[0]["command"]
    assert cmd.startswith("/draft-license")
    assert "our_role=licensor" in cmd  # 乙方 → licensor in License
    assert 'licensee="Eli Lilly"' in cmd
    assert 'asset_name="PEG-001 (NSCLC)"' in cmd


def test_suggested_commands_mta_jiafang_inverts_role():
    """If we were the recipient (甲方) in MTA, we're the licensee in License."""
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="mta",
        party_position="甲方",
        contract_text="x",
        counterparty="Stanford",
    )
    sc = svc._build_suggested_commands(inp)
    cmd = sc[0]["command"]
    assert "our_role=licensee" in cmd
    assert 'licensor="Stanford"' in cmd


def test_suggested_commands_mta_without_counterparty():
    """MTA with no counterparty still emits the chip (counterparty field omitted)."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="mta", party_position="甲方", contract_text="x")
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 1
    assert sc[0]["slug"] == "draft-license"
    assert "our_role=licensee" in sc[0]["command"]
    # Without counterparty, no licensor= or licensee= prefilled (other than ours)
    assert 'licensor="' not in sc[0]["command"]


def test_suggested_commands_ts_routes_to_draft_license_and_draft_codev():
    """Stage 6: TS review → offer two definitive-agreement drafting chips.

    Both chips route to /draft-X services, NOT /legal review. The
    audit (test_chip_routing_audit) prevents any regression that
    re-routes a "Draft X" labeled chip back to legal-review.
    """
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="ts",
        party_position="乙方",  # we granted (licensor)
        contract_text="x",
        counterparty="Eli Lilly",
        project_name="PEG-001 (NSCLC)",
    )
    sc = svc._build_suggested_commands(inp)
    slugs = [c["slug"] for c in sc]
    assert slugs == ["draft-license", "draft-codev"]

    license_chip = next(c for c in sc if c["slug"] == "draft-license")
    assert license_chip["command"].startswith("/draft-license")
    assert "our_role=licensor" in license_chip["command"]
    assert 'licensee="Eli Lilly"' in license_chip["command"]
    assert 'asset_name="PEG-001 (NSCLC)"' in license_chip["command"]

    codev_chip = next(c for c in sc if c["slug"] == "draft-codev")
    assert codev_chip["command"].startswith("/draft-codev")
    assert "our_role=party_b" in codev_chip["command"]  # 乙方 → party_b
    assert 'party_a="Eli Lilly"' in codev_chip["command"]
    assert 'program_name="PEG-001 (NSCLC)"' in codev_chip["command"]


def test_suggested_commands_ts_without_counterparty():
    """TS with no counterparty still emits chips (counterparty field omitted)."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="ts", party_position="甲方", contract_text="x")
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 2
    for c in sc:
        assert "counterparty" not in c["command"]


def test_suggested_commands_ts_labels():
    """Chip labels are human-readable."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="ts", party_position="乙方", contract_text="x")
    sc = svc._build_suggested_commands(inp)
    labels = {c["label"] for c in sc}
    assert "Draft License Agreement" in labels
    assert "Draft Co-Dev Agreement" in labels


def test_chat_tool_input_schema_is_well_formed():
    svc = LegalReviewService()
    schema = svc.chat_tool_input_schema
    assert schema["type"] == "object"
    assert "contract_type" in schema["properties"]
    # Both contract_text and filename should be optional in the schema —
    # the cross-field requirement is enforced at pydantic level, not via
    # JSON Schema's "required" array.
    assert "required" in schema
    assert "contract_text" not in schema["required"]
    assert "filename" not in schema["required"]
    assert "contract_type" in schema["required"]
    assert "party_position" in schema["required"]


# ─────────────────────────────────────────────────────────────
# /draft-X → /legal lifecycle handoff via source_task_id
# ─────────────────────────────────────────────────────────────


class TestSourceTaskIdHandoff:
    """The /draft-X chip emits `source_task_id={ctx.task_id}` so /legal
    can pull the just-generated draft markdown directly. Without this,
    clicking the chip lands the user on a /legal flow that still
    demands contract_text (closed-loop bug)."""

    def test_input_accepts_source_task_id_alone(self):
        from services.reports.legal_review import LegalReviewInput

        inp = LegalReviewInput(
            contract_type="spa",
            party_position="甲方",
            source_task_id="abc123def",
        )
        assert inp.source_task_id == "abc123def"
        assert inp.contract_text is None
        assert inp.filename is None

    def test_input_rejects_when_all_three_sources_empty(self):
        import pytest
        from services.reports.legal_review import LegalReviewInput

        with pytest.raises(ValueError, match="contract_text|filename|source_task_id"):
            LegalReviewInput(contract_type="spa", party_position="甲方")

    def test_schema_advertises_source_task_id(self):
        from services.reports.legal_review import LegalReviewService

        svc = LegalReviewService()
        props = svc.chat_tool_input_schema["properties"]
        assert "source_task_id" in props
        assert props["source_task_id"]["type"] == "string"
        # description must mention /draft-X so the LLM extractor picks it up
        assert "draft-X" in props["source_task_id"]["description"]

    def test_resolve_prefers_filename_over_text_over_task_id(self, tmp_path):
        """Resolution order is filename > contract_text > source_task_id.
        This keeps a manually re-pasted contract winning over a stale
        chip-injected source_task_id reference.
        """
        from services.reports.legal_review import LegalReviewInput, LegalReviewService

        svc = LegalReviewService()

        class FakeCtx:
            task_id = "current-task"
            user_id = "u1"

            def log(self, msg):
                pass

        # 1. filename takes priority — but extract_contract_text would need a
        #    real file; we don't test that path here. Instead test text > task_id.
        inp = LegalReviewInput(
            contract_type="spa",
            party_position="甲方",
            contract_text="pasted body",
            source_task_id="some-task",
        )
        text, label = svc._resolve_contract_text(inp, FakeCtx())
        assert text == "pasted body"
        assert label == "pasted"

    def test_resolve_from_task_when_only_task_id_set(self, tmp_path, monkeypatch):
        """When only source_task_id is set, resolver reads the .md file
        from REPORTS_DIR/{task_id}/."""
        from services.reports import legal_review as lr_mod
        from services.reports.legal_review import LegalReviewInput, LegalReviewService

        # Build a fake REPORTS_DIR with a markdown file
        fake_reports_dir = tmp_path / "reports"
        task_id = "fake-spa-task"
        task_dir = fake_reports_dir / task_id
        task_dir.mkdir(parents=True)
        md_filename = "draft_spa_test.md"
        (task_dir / md_filename).write_text("# SPA Draft — TargetCo\n\nbody...\n", encoding="utf-8")

        # Stub get_task to return our fake row
        def fake_get_task(tid):
            assert tid == task_id
            return {
                "task_id": tid,
                "user_id": "u1",
                "result": {"files": [{"format": "md", "filename": md_filename}]},
            }

        monkeypatch.setattr("services.report_builder.get_task", fake_get_task)
        monkeypatch.setattr("services.report_builder.REPORTS_DIR", fake_reports_dir)
        # Also monkeypatch the imports inside _read_markdown_from_task
        monkeypatch.setattr(lr_mod, "_MAX_CONTRACT_CHARS", 80_000)

        svc = LegalReviewService()
        inp = LegalReviewInput(
            contract_type="spa",
            party_position="甲方",
            source_task_id=task_id,
        )

        class FakeCtx:
            task_id = "current-task"
            user_id = "u1"
            _logs = []

            def log(self, msg):
                self._logs.append(msg)

        ctx = FakeCtx()
        text, label = svc._resolve_contract_text(inp, ctx)
        assert "SPA Draft — TargetCo" in text
        assert label == f"task:{task_id}"
        # Should have logged the resolution for debugging
        assert any(task_id in m for m in ctx._logs)

    def test_resolve_from_task_rejects_other_users_task(self, tmp_path, monkeypatch):
        """Defense in depth: source_task_id must belong to the same user."""
        import pytest
        from services.reports.legal_review import LegalReviewInput, LegalReviewService

        def fake_get_task(tid):
            return {"task_id": tid, "user_id": "other-user", "result": {"files": []}}

        monkeypatch.setattr("services.report_builder.get_task", fake_get_task)

        svc = LegalReviewService()
        inp = LegalReviewInput(
            contract_type="spa",
            party_position="甲方",
            source_task_id="someone-elses-task",
        )

        class FakeCtx:
            task_id = "current-task"
            user_id = "u1"

            def log(self, msg):
                pass

        with pytest.raises(RuntimeError, match="不属于当前用户"):
            svc._resolve_contract_text(inp, FakeCtx())

    def test_resolve_from_task_raises_when_task_not_found(self, monkeypatch):
        import pytest
        from services.reports.legal_review import LegalReviewInput, LegalReviewService

        monkeypatch.setattr("services.report_builder.get_task", lambda tid: None)

        svc = LegalReviewService()
        inp = LegalReviewInput(
            contract_type="spa",
            party_position="甲方",
            source_task_id="nonexistent",
        )

        class FakeCtx:
            task_id = "current-task"
            user_id = "u1"

            def log(self, msg):
                pass

        with pytest.raises(RuntimeError, match="找不到来源任务"):
            svc._resolve_contract_text(inp, FakeCtx())
