"""Unit tests for services/enrich/runner — the core of S-005's
extraction. Covers the pure parse helpers + the allowlist-gated
DB write path. Network / subprocess / threading paths are out of
scope (those deserve integration tests)."""

from __future__ import annotations

from unittest.mock import patch


class TestExtractEntity:
    """_extract_entity is the first gate — it decides which prompt
    template + table the LLM output goes to. Regressions here silently
    route writes to the wrong table."""

    def test_clinical_keyword_maps_to_clinical(self):
        from services.enrich.runner import _extract_entity

        assert _extract_entity("临床试验 NCT123")[0] == "clinical"
        assert _extract_entity("clinical trial foo")[0] == "clinical"

    def test_deal_keyword_maps_to_deal(self):
        from services.enrich.runner import _extract_entity

        assert _extract_entity("BMS 交易 analysis")[0] == "deal"
        assert _extract_entity("deal: Pfizer-X")[0] == "deal"

    def test_asset_pattern_with_parenthesized_company(self):
        """'Drug-X (Foo Bio)' → asset=Drug-X, company=Foo Bio."""
        from services.enrich.runner import _extract_entity

        assert _extract_entity("Drug-X (Foo Bio)") == ("asset", "Drug-X", "Foo Bio")

    def test_asset_pattern_strips_leading_action_verbs(self):
        from services.enrich.runner import _extract_entity

        # "对资产 Drug-X (Foo) 评估..." → asset pattern
        assert _extract_entity("对资产 Drug-X (Foo Bio) 做四象限评估") == (
            "asset",
            "Drug-X",
            "Foo Bio",
        )

    def test_fallthrough_is_company(self):
        from services.enrich.runner import _extract_entity

        assert _extract_entity("Pfizer") == ("company", "Pfizer", "")


class TestWriteEnrichedFields:
    """The safety gate between LLM output and the CRM. Three rules:
    1. Reject columns not in the allowlist (LLM hallucination guard)
    2. Drop empty / placeholder values
    3. Never clobber an existing non-empty value
    """

    def _setup(self, existing_row):
        """Returns patches for query + update_row; existing_row goes
        back as the 'current CRM row' the writer compares against."""
        query_patch = patch("services.enrich.runner.query")
        update_patch = patch("services.enrich.runner.update_row")
        return query_patch, update_patch, existing_row

    def test_filters_disallowed_columns(self):
        from services.enrich.runner import _write_enriched_fields

        existing = {"客户名称": "Foo", "所处国家": ""}
        with (
            patch("services.enrich.runner.query") as mock_q,
            patch("services.enrich.runner.update_row") as mock_upd,
        ):
            mock_q.return_value = [existing]
            # "rogue_column" is NOT in VALID_COMPANY_COLS — must be dropped
            fields_written = _write_enriched_fields(
                "company",
                "Foo",
                "",
                {"所处国家": "USA", "rogue_column": "payload"},
            )

        assert fields_written == 1  # only 所处国家 gets through
        args = mock_upd.call_args.args
        assert args[0] == "公司"
        assert args[1] == "Foo"
        assert args[2] == {"所处国家": "USA"}
        assert "rogue_column" not in args[2]

    def test_drops_empty_and_placeholder_values(self):
        from services.enrich.runner import _write_enriched_fields

        existing = {"所处国家": "", "疾病领域": "", "Ticker": ""}
        with (
            patch("services.enrich.runner.query") as mock_q,
            patch("services.enrich.runner.update_row") as mock_upd,
        ):
            mock_q.return_value = [existing]
            _write_enriched_fields(
                "company",
                "Foo",
                "",
                {
                    "所处国家": "",
                    "疾病领域": "N/A",
                    "Ticker": "未知",
                    "客户类型": "Pharma",  # real value — should write
                },
            )

        # Only 客户类型 makes it through
        assert mock_upd.call_args.args[2] == {"客户类型": "Pharma"}

    def test_never_overwrites_existing_non_empty_fields(self):
        """'宁空勿错' — if a column already has content, trust it over
        the LLM's guess."""
        from services.enrich.runner import _write_enriched_fields

        existing = {"所处国家": "USA", "疾病领域": ""}
        with (
            patch("services.enrich.runner.query") as mock_q,
            patch("services.enrich.runner.update_row") as mock_upd,
        ):
            mock_q.return_value = [existing]
            _write_enriched_fields(
                "company",
                "Foo",
                "",
                {
                    "所处国家": "China",  # would clobber — drop
                    "疾病领域": "Oncology",  # currently empty — write
                },
            )

        written = mock_upd.call_args.args[2]
        assert written == {"疾病领域": "Oncology"}
        assert "所处国家" not in written

    def test_dash_is_treated_as_empty_for_overwrite(self):
        """Analysts use '-' as a placeholder; treat it as empty so
        enrichment can fill it."""
        from services.enrich.runner import _write_enriched_fields

        existing = {"所处国家": "-"}
        with (
            patch("services.enrich.runner.query") as mock_q,
            patch("services.enrich.runner.update_row") as mock_upd,
        ):
            mock_q.return_value = [existing]
            _write_enriched_fields("company", "Foo", "", {"所处国家": "USA"})

        assert mock_upd.call_args.args[2] == {"所处国家": "USA"}

    def test_asset_uses_composite_pk(self):
        """Asset rows are keyed by (资产名称, 所属客户) — the update
        call must pass both, not just the asset name."""
        from services.enrich.runner import _write_enriched_fields

        existing = {"靶点": ""}
        with (
            patch("services.enrich.runner.query") as mock_q,
            patch("services.enrich.runner.update_row") as mock_upd,
        ):
            mock_q.return_value = [existing]
            _write_enriched_fields("asset", "Drug-X", "Foo Bio", {"靶点": "EGFR"})

        args = mock_upd.call_args.args
        assert args[0] == "资产"
        assert args[1] == {"pk1": "Drug-X", "pk2": "Foo Bio"}

    def test_clinical_entity_skips_db_write(self):
        """Clinical / deal tasks produce text analysis only — no
        structured fields to persist, so the write step must short-
        circuit before touching crm_store."""
        from services.enrich.runner import _write_enriched_fields

        with (
            patch("services.enrich.runner.query") as mock_q,
            patch("services.enrich.runner.update_row") as mock_upd,
        ):
            fields_written = _write_enriched_fields("clinical", "X", "", {"靶点": "EGFR"})

        assert fields_written == 0
        mock_q.assert_not_called()
        mock_upd.assert_not_called()


class TestPublicAPI:
    """start_task / get_task / list_tasks over the in-memory _tasks
    dict — the surface routers/tasks.py calls."""

    def test_get_task_unknown_returns_none(self):
        from services.enrich.runner import get_task

        assert get_task("does-not-exist-XXXX") is None

    def test_list_tasks_default_limit_and_recency_order(self):
        import services.enrich.runner as runner

        # Seed the dict directly — avoids threading.
        original = runner._tasks.copy()
        try:
            runner._tasks.clear()
            runner._tasks["old"] = {"id": "old", "created_at": 1_000.0}
            runner._tasks["new"] = {"id": "new", "created_at": 2_000.0}
            result = runner.list_tasks()
            assert [t["id"] for t in result] == ["new", "old"]

            # limit parameter respected
            assert len(runner.list_tasks(limit=1)) == 1
        finally:
            runner._tasks.clear()
            runner._tasks.update(original)
