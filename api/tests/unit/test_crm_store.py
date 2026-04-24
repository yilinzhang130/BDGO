"""Pure-function tests for crm_store.py.

These are the sanitization + parsing gates that run on every query
path — any regression here is a silent data-integrity or DoS issue.
Testing the real functions (no mocks needed since they're pure).
"""

from __future__ import annotations


class TestLikeEscape:
    """\
    Wildcards in LIKE patterns are attacker-controlled surface: a '%' from
    a user's search input would match ANYTHING, a '_' becomes a regex
    metachar, and a long string of '%%%%' forces a full-table scan.
    """

    def test_plain_text_unchanged(self):
        from crm_store import like_escape

        assert like_escape("Pfizer") == "Pfizer"
        assert like_escape("KRAS G12C") == "KRAS G12C"

    def test_percent_escaped(self):
        from crm_store import like_escape

        assert like_escape("50%") == "50\\%"
        assert like_escape("%ABC%") == "\\%ABC\\%"

    def test_underscore_escaped(self):
        from crm_store import like_escape

        assert like_escape("A_B") == "A\\_B"

    def test_backslash_escaped_before_others(self):
        """Backslash must be doubled FIRST; otherwise the added \\ in
        subsequent steps would also be treated as the escape char."""
        from crm_store import like_escape

        assert like_escape("a\\b") == "a\\\\b"
        # Combined: backslash + percent — the backslash must remain
        # literal AFTER escaping the percent.
        assert like_escape("a\\%b") == "a\\\\\\%b"

    def test_empty_string(self):
        from crm_store import like_escape

        assert like_escape("") == ""

    def test_none_treated_as_empty(self):
        """Callers sometimes pass None from optional query params; must
        not crash."""
        from crm_store import like_escape

        assert like_escape(None) == ""  # type: ignore[arg-type]


class TestLikeContains:
    def test_wraps_in_percent_signs(self):
        from crm_store import like_contains

        assert like_contains("foo") == "%foo%"

    def test_strips_whitespace(self):
        from crm_store import like_contains

        assert like_contains("  hello  ") == "%hello%"

    def test_escapes_user_wildcards(self):
        from crm_store import like_contains

        # User's '%' inside input stays literal; outer %s are the LIKE
        # wildcards.
        assert like_contains("50%") == "%50\\%%"

    def test_dos_clamp(self):
        """A 200-char input gets trimmed to the 100-char default cap —
        otherwise a malicious caller could force expensive index
        scans across every column on every search."""
        from crm_store import like_contains

        long_input = "x" * 200
        result = like_contains(long_input)
        # Outer two '%' + 100 x's
        assert result == "%" + "x" * 100 + "%"

    def test_respects_custom_max_len(self):
        from crm_store import like_contains

        assert like_contains("abcdef", max_len=3) == "%abc%"

    def test_empty_input_still_wraps(self):
        from crm_store import like_contains

        # %% matches everything — documented behavior; callers must
        # short-circuit empty inputs at the query-build site, not
        # here.
        assert like_contains("") == "%%"


class TestQmarkToPercent:
    """Rewrites ``?`` placeholders to psycopg2 ``%s`` form. The tricky
    part is leaving quoted ``?`` characters alone — a literal
    question mark inside a string or identifier must not be mistaken
    for a placeholder."""

    def test_basic_placeholder(self):
        from crm_store import _qmark_to_percent

        assert _qmark_to_percent("SELECT * FROM t WHERE a = ?") == ("SELECT * FROM t WHERE a = %s")

    def test_multiple_placeholders(self):
        from crm_store import _qmark_to_percent

        assert _qmark_to_percent("a = ? AND b = ?") == "a = %s AND b = %s"

    def test_qmark_inside_single_quoted_string_preserved(self):
        """A literal '?' inside a string must NOT be converted — that
        would break queries that legitimately contain question marks
        in string literals."""
        from crm_store import _qmark_to_percent

        assert _qmark_to_percent("WHERE x = 'what?' AND y = ?") == ("WHERE x = 'what?' AND y = %s")

    def test_qmark_inside_double_quoted_identifier_preserved(self):
        from crm_store import _qmark_to_percent

        assert _qmark_to_percent('SELECT "col?name" FROM t WHERE a = ?') == (
            'SELECT "col?name" FROM t WHERE a = %s'
        )

    def test_no_placeholders_is_identity(self):
        from crm_store import _qmark_to_percent

        sql = "SELECT 1"
        assert _qmark_to_percent(sql) == sql


class TestParseNumeric:
    def test_int_passthrough(self):
        from crm_store import parse_numeric

        assert parse_numeric(42) == 42.0

    def test_float_passthrough(self):
        from crm_store import parse_numeric

        assert parse_numeric(3.14) == 3.14

    def test_plain_numeric_string(self):
        from crm_store import parse_numeric

        assert parse_numeric("300.0") == 300.0

    def test_dollar_prefix(self):
        from crm_store import parse_numeric

        assert parse_numeric("$1.25") == 1.25

    def test_billion_suffix_converts_to_millions(self):
        """CRM stores deal amounts in $M; "$1.25B" must come out as
        1250.0 (= $1.25B in millions), not 1.25."""
        from crm_store import parse_numeric

        assert parse_numeric("$1.25B") == 1250.0

    def test_approx_tilde_prefix(self):
        """Analysts sometimes write '~6.8B' for 'approximately'."""
        from crm_store import parse_numeric

        assert parse_numeric("~6.8B") == 6800.0

    def test_none_returns_none(self):
        from crm_store import parse_numeric

        assert parse_numeric(None) is None

    def test_empty_string_returns_none(self):
        from crm_store import parse_numeric

        assert parse_numeric("") is None
        assert parse_numeric("   ") is None

    def test_non_numeric_string_returns_none(self):
        from crm_store import parse_numeric

        assert parse_numeric("TBD") is None
