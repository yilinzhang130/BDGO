"""Tests for the deterministic kv-pair pre-parser + LLM fallback in
``services.external.llm.extract_params_from_text``.

Background: chip handoffs emit slash commands with explicit key=value
pairs (e.g. `/legal contract_type=spa source_task_id=abc123 counterparty="Pfizer"`).
Sending these through the LLM extractor was wasted latency + a
hallucination risk. The deterministic pre-parser handles them without
LLM, falling back to the LLM only for free-text portions.
"""

from __future__ import annotations

from unittest.mock import patch

from services.external.llm import extract_kv_pairs, extract_params_from_text

# ── Schemas used across tests ────────────────────────────────


_LEGAL_SCHEMA = {
    "type": "object",
    "properties": {
        "contract_type": {"type": "string"},
        "party_position": {"type": "string"},
        "source_task_id": {"type": "string"},
        "counterparty": {"type": "string"},
        "project_name": {"type": "string"},
        "focus": {"type": "string"},
    },
    "required": ["contract_type", "party_position"],
}

_SPA_SCHEMA = {
    "type": "object",
    "properties": {
        "buyer": {"type": "string"},
        "seller": {"type": "string"},
        "target_company": {"type": "string"},
        "our_role": {"type": "string"},
        "indemnity_cap_pct_of_price": {"type": "number"},
        "indemnity_basket_usd_mm": {"type": "number"},
        "indemnity_survival_months": {"type": "integer"},
        "requires_hsr_approval": {"type": "boolean"},
        "has_mac_clause": {"type": "boolean"},
    },
    "required": ["buyer", "seller", "target_company", "our_role"],
}


# ─────────────────────────────────────────────────────────────
# extract_kv_pairs — pure parser unit tests
# ─────────────────────────────────────────────────────────────


class TestExtractKvPairs:
    def test_empty_text_returns_empty(self):
        assert extract_kv_pairs("", _LEGAL_SCHEMA["properties"]) == ({}, "")

    def test_simple_unquoted_pair(self):
        params, residual = extract_kv_pairs("contract_type=spa", _LEGAL_SCHEMA["properties"])
        assert params == {"contract_type": "spa"}
        assert residual == ""

    def test_double_quoted_value_with_spaces(self):
        params, residual = extract_kv_pairs(
            'counterparty="Pfizer Inc."', _LEGAL_SCHEMA["properties"]
        )
        assert params == {"counterparty": "Pfizer Inc."}
        assert residual == ""

    def test_single_quoted_value(self):
        params, residual = extract_kv_pairs("counterparty='Pfizer'", _LEGAL_SCHEMA["properties"])
        assert params == {"counterparty": "Pfizer"}

    def test_chip_style_full_command(self):
        """The exact shape of a /draft-spa → /legal chip handoff."""
        text = (
            'contract_type=spa party_position="甲方" source_task_id=abc123 '
            'counterparty="Founders & VCs" project_name="TargetCo (stock_purchase)"'
        )
        params, residual = extract_kv_pairs(text, _LEGAL_SCHEMA["properties"])
        assert params == {
            "contract_type": "spa",
            "party_position": "甲方",
            "source_task_id": "abc123",
            "counterparty": "Founders & VCs",
            "project_name": "TargetCo (stock_purchase)",
        }
        # Everything consumed → empty residual → no LLM call needed
        assert residual == ""

    def test_unknown_key_filtered_out(self):
        """Stray identifiers that aren't in the schema are dropped — defends
        against the LLM-only path's hallucinated-field problem."""
        text = "contract_type=spa hallucinated_field=oops party_position=甲方"
        params, residual = extract_kv_pairs(text, _LEGAL_SCHEMA["properties"])
        assert params == {"contract_type": "spa", "party_position": "甲方"}
        # The unknown pair stays in residual — caller's LLM might use it as context
        assert "hallucinated_field=oops" in residual

    def test_residual_preserves_free_text(self):
        """Mixed chip + free text: kv pairs extracted, free text remains."""
        text = "contract_type=spa Pfizer 收购 TargetCo 5亿美元"
        params, residual = extract_kv_pairs(text, _LEGAL_SCHEMA["properties"])
        assert params == {"contract_type": "spa"}
        assert "Pfizer 收购 TargetCo 5亿美元" in residual

    def test_boolean_coercion(self):
        params, _ = extract_kv_pairs(
            "requires_hsr_approval=true has_mac_clause=false",
            _SPA_SCHEMA["properties"],
        )
        assert params == {"requires_hsr_approval": True, "has_mac_clause": False}

    def test_boolean_yes_no_aliases(self):
        params, _ = extract_kv_pairs(
            "requires_hsr_approval=yes has_mac_clause=no",
            _SPA_SCHEMA["properties"],
        )
        assert params["requires_hsr_approval"] is True
        assert params["has_mac_clause"] is False

    def test_integer_coercion(self):
        params, _ = extract_kv_pairs("indemnity_survival_months=24", _SPA_SCHEMA["properties"])
        assert params == {"indemnity_survival_months": 24}
        assert isinstance(params["indemnity_survival_months"], int)

    def test_number_coercion(self):
        params, _ = extract_kv_pairs(
            "indemnity_cap_pct_of_price=12.5 indemnity_basket_usd_mm=0.5",
            _SPA_SCHEMA["properties"],
        )
        assert params["indemnity_cap_pct_of_price"] == 12.5
        assert params["indemnity_basket_usd_mm"] == 0.5

    def test_uncoerceable_value_falls_back_to_string(self):
        """If `indemnity_survival_months=abc` (non-int), keep raw string —
        the caller's pydantic model will raise a clear validation error
        rather than us silently coercing to a default."""
        params, _ = extract_kv_pairs("indemnity_survival_months=abc", _SPA_SCHEMA["properties"])
        assert params == {"indemnity_survival_months": "abc"}


# ─────────────────────────────────────────────────────────────
# extract_params_from_text — orchestration tests
# ─────────────────────────────────────────────────────────────


class TestExtractParamsFromText:
    def test_chip_command_skips_llm(self):
        """Pure kv input → no LLM call. This is the chip-handoff fast path."""
        text = 'contract_type=spa party_position="甲方" source_task_id=abc123 counterparty="Pfizer"'
        with patch("services.external.llm.call_llm_sync") as mock_llm:
            params = extract_params_from_text(text, _LEGAL_SCHEMA, "Legal Review")

        mock_llm.assert_not_called()
        assert params == {
            "contract_type": "spa",
            "party_position": "甲方",
            "source_task_id": "abc123",
            "counterparty": "Pfizer",
        }

    def test_free_text_still_goes_to_llm(self):
        """No kv pairs → falls through to LLM extractor."""
        with patch(
            "services.external.llm.call_llm_sync",
            return_value='{"contract_type": "spa", "party_position": "甲方"}',
        ) as mock_llm:
            params = extract_params_from_text(
                "Pfizer 收购 TargetCo SPA 我方甲方", _LEGAL_SCHEMA, "Legal Review"
            )

        mock_llm.assert_called_once()
        assert params == {"contract_type": "spa", "party_position": "甲方"}

    def test_mixed_kv_and_free_text_calls_llm_with_residual_only(self):
        """When user types `/draft-spa buyer=Pfizer 我方角色买方` the kv pair
        is extracted deterministically and only the Chinese fragment is
        sent to the LLM."""
        captured: dict = {}

        def capture(*, system, messages, **kw):
            captured["llm_input"] = messages[0]["content"]
            return '{"our_role": "buyer"}'

        with patch("services.external.llm.call_llm_sync", side_effect=capture):
            params = extract_params_from_text(
                'buyer="Pfizer" seller="TargetCo" target_company="TargetCo" 我方角色买方',
                _SPA_SCHEMA,
                "Draft SPA",
            )

        # LLM was called, but only with the residual non-kv text
        assert "Pfizer" not in captured["llm_input"], (
            f"LLM should not have seen kv-extracted data: {captured['llm_input']!r}"
        )
        assert "我方角色买方" in captured["llm_input"]
        # Final merged params include both deterministic + LLM extractions
        assert params["buyer"] == "Pfizer"
        assert params["seller"] == "TargetCo"
        assert params["our_role"] == "buyer"

    def test_kv_wins_on_collision(self):
        """If the LLM hallucinates a value for a field already locked in by
        the kv parser, the kv value wins."""

        def capture(*, system, messages, **kw):
            # LLM tries to set our_role=seller, but kv set it to buyer
            return '{"our_role": "seller"}'

        with patch("services.external.llm.call_llm_sync", side_effect=capture):
            params = extract_params_from_text(
                "our_role=buyer plus extra free text", _SPA_SCHEMA, "Draft SPA"
            )

        assert params["our_role"] == "buyer", (
            "deterministic kv parse must override hallucinated LLM value"
        )

    def test_empty_input_returns_empty(self):
        with patch("services.external.llm.call_llm_sync") as mock_llm:
            params = extract_params_from_text("   ", _LEGAL_SCHEMA, "Legal Review")
        mock_llm.assert_not_called()
        assert params == {}

    def test_llm_failure_preserves_kv_params(self):
        """If the LLM call raises, deterministic kv params still survive —
        partial result is better than an empty result."""

        def fail(**kw):
            raise RuntimeError("LLM down")

        with patch("services.external.llm.call_llm_sync", side_effect=fail):
            params = extract_params_from_text(
                "buyer=Pfizer some free-text the llm would have extracted",
                _SPA_SCHEMA,
                "Draft SPA",
            )

        assert params == {"buyer": "Pfizer"}

    def test_llm_returns_garbage_preserves_kv_params(self):
        with patch("services.external.llm.call_llm_sync", return_value="lol not json"):
            params = extract_params_from_text("buyer=Pfizer free text", _SPA_SCHEMA, "Draft SPA")
        assert params == {"buyer": "Pfizer"}
