"""Unit tests for planner.py — the pure helpers that decide what the
planner LLM said and how to hand its plan to the execution phase.
LLM I/O (generate_plan, summarize_history) is out of scope for unit
tests — exercised by integration tests with real model calls.
"""

from __future__ import annotations


class TestParsePlanJson:
    """_parse_plan_json is the gate between raw LLM text and the plan
    contract. Every branch of its validation is a silent failure mode
    if we don't test it — the caller just gets back None and falls
    back to no-plan execution."""

    def test_valid_plan_parses(self):
        from planner import _parse_plan_json

        raw = """{
            "title": "分析 AbbVie",
            "summary": "扫描管线 + 匹配中国资产",
            "steps": [
                {"id": "s1", "title": "扫描管线", "required": true},
                {"id": "s2", "title": "匹配资产"}
            ]
        }"""
        plan = _parse_plan_json(raw)
        assert plan is not None
        assert plan["title"] == "分析 AbbVie"
        assert len(plan["steps"]) == 2
        assert plan["steps"][0]["id"] == "s1"
        assert plan["steps"][0]["required"] is True
        # plan_id is attached downstream (16 hex chars)
        assert len(plan["plan_id"]) == 16

    def test_strips_markdown_fences(self):
        """Planners occasionally wrap JSON in ```json ... ``` despite
        instructions. The parser must tolerate it."""
        from planner import _parse_plan_json

        raw = """```json
{"title": "X", "steps": [{"id": "s1", "title": "step"}]}
```"""
        plan = _parse_plan_json(raw)
        assert plan is not None
        assert plan["title"] == "X"

    def test_extracts_json_surrounded_by_prose(self):
        """If the model prepends/appends chatter, take the first {...}."""
        from planner import _parse_plan_json

        raw = (
            'Here is the plan: {"title": "X", "steps": [{"id": "s1", "title": "go"}]} '
            "Let me know if you need changes."
        )
        plan = _parse_plan_json(raw)
        assert plan is not None
        assert plan["title"] == "X"

    def test_unparseable_returns_none(self):
        from planner import _parse_plan_json

        assert _parse_plan_json("not json at all") is None
        assert _parse_plan_json("") is None
        assert _parse_plan_json("{broken json,,,}") is None

    def test_empty_steps_returns_none(self):
        """An empty plan is useless — caller should fall back to
        normal execution instead of showing a zero-step UI."""
        from planner import _parse_plan_json

        assert _parse_plan_json('{"title": "X", "steps": []}') is None

    def test_missing_steps_field_returns_none(self):
        from planner import _parse_plan_json

        assert _parse_plan_json('{"title": "X"}') is None

    def test_steps_not_list_returns_none(self):
        from planner import _parse_plan_json

        assert _parse_plan_json('{"title": "X", "steps": "not a list"}') is None

    def test_non_dict_toplevel_returns_none(self):
        """Model returns a bare list instead of a dict — reject."""
        from planner import _parse_plan_json

        assert _parse_plan_json('[{"id": "s1"}]') is None

    def test_non_dict_step_is_skipped(self):
        """A malformed step entry shouldn't poison the whole plan —
        normalize skips it."""
        from planner import _parse_plan_json

        raw = """{
            "title": "X",
            "steps": [
                "not a dict step",
                {"id": "s2", "title": "valid"}
            ]
        }"""
        plan = _parse_plan_json(raw)
        assert plan is not None
        assert len(plan["steps"]) == 1
        assert plan["steps"][0]["id"] == "s2"

    def test_step_defaults_applied(self):
        """A minimal step (just title) gets sensible defaults so the
        UI doesn't have to handle None-vs-missing."""
        from planner import _parse_plan_json

        raw = '{"title": "X", "steps": [{"title": "t"}]}'
        plan = _parse_plan_json(raw)
        assert plan is not None
        step = plan["steps"][0]
        assert step["id"] == "s1"  # synthesized from index
        assert step["description"] == ""
        assert step["tools_expected"] == []
        assert step["required"] is False
        assert step["default_selected"] is True
        assert step["estimated_seconds"] == 30

    def test_only_non_dict_steps_returns_none(self):
        """If the list has only malformed entries, the whole plan is
        useless — don't return an empty-steps plan."""
        from planner import _parse_plan_json

        raw = '{"title": "X", "steps": ["bad", 123, null]}'
        assert _parse_plan_json(raw) is None

    def test_tools_expected_coerced_to_strings(self):
        """Model occasionally emits non-string entries in tools_expected
        (e.g. ints). Coerce defensively — they're display-only."""
        from planner import _parse_plan_json

        raw = (
            '{"title": "X", "steps": [{"title": "t", '
            '"tools_expected": ["search_companies", 42, ""]}]}'
        )
        plan = _parse_plan_json(raw)
        assert plan is not None
        # The empty string is filtered; the int is coerced.
        assert plan["steps"][0]["tools_expected"] == ["search_companies", "42"]


class TestRecentTextOnly:
    """_recent_text_only strips tool_use/tool_result blocks so the
    planner sees a clean text-only history."""

    def test_extracts_text_from_structured_content(self):
        from planner import _recent_text_only

        history = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "分析 AbbVie"}],
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "search_companies"},
                    {"type": "text", "text": "找到了 23 个资产"},
                ],
            },
        ]
        out = _recent_text_only(history, turns=2)
        assert out == [
            {"role": "user", "content": "分析 AbbVie"},
            {"role": "assistant", "content": "找到了 23 个资产"},
        ]

    def test_trims_to_last_n_pairs(self):
        """turns=2 means last 4 messages, not last 2."""
        from planner import _recent_text_only

        history = [
            {"role": "user", "content": "m1"},
            {"role": "assistant", "content": "m2"},
            {"role": "user", "content": "m3"},
            {"role": "assistant", "content": "m4"},
            {"role": "user", "content": "m5"},
            {"role": "assistant", "content": "m6"},
        ]
        out = _recent_text_only(history, turns=2)
        assert [m["content"] for m in out] == ["m3", "m4", "m5", "m6"]

    def test_drops_system_role_messages(self):
        """Planner is a pristine context — only user/assistant should
        make it into the short history."""
        from planner import _recent_text_only

        history = [
            {"role": "system", "content": "system notes"},
            {"role": "user", "content": "hello"},
        ]
        out = _recent_text_only(history, turns=2)
        assert [m["role"] for m in out] == ["user"]

    def test_drops_empty_text_messages(self):
        """Tool-only assistant turns (no text blocks) shouldn't leak
        as empty-string messages — planner would count them as turns."""
        from planner import _recent_text_only

        history = [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "search"}],
            },
            {"role": "user", "content": "hello"},
        ]
        out = _recent_text_only(history, turns=2)
        assert out == [{"role": "user", "content": "hello"}]

    def test_handles_plain_string_content(self):
        """Some clients send content as a plain string, not a list."""
        from planner import _recent_text_only

        history = [{"role": "user", "content": "plain text"}]
        out = _recent_text_only(history, turns=2)
        assert out == [{"role": "user", "content": "plain text"}]

    def test_handles_none_content(self):
        """Defensive: ``None`` content should be skipped, not crash."""
        from planner import _recent_text_only

        history = [
            {"role": "user", "content": None},
            {"role": "assistant", "content": "valid"},
        ]
        out = _recent_text_only(history, turns=2)
        assert out == [{"role": "assistant", "content": "valid"}]


class TestBuildPlanConstraint:
    """build_plan_constraint emits the system-prompt suffix injected
    when the user has approved a plan — this is how the execution LLM
    learns which steps to stick to."""

    def test_includes_all_selected_steps(self):
        from planner import build_plan_constraint

        selected = [
            {"id": "s1", "title": "扫描管线"},
            {"id": "s3", "title": "提交建议"},
        ]
        text = build_plan_constraint("分析 AbbVie", selected)
        assert "分析 AbbVie" in text
        assert "s1: 扫描管线" in text
        assert "s3: 提交建议" in text

    def test_only_selected_steps_appear(self):
        """If the user unchecks a step, it must not show up in the
        constraint — otherwise the executor runs it anyway."""
        from planner import build_plan_constraint

        selected = [{"id": "s2", "title": "kept"}]
        text = build_plan_constraint("X", selected)
        assert "s2: kept" in text
        assert "dropped" not in text


class TestToolInventoryStaysSynced:
    """The planner system prompt lists every available tool by name.
    If a service is registered but not listed here, the planner LLM
    won't know it exists and won't propose using it — silent feature
    invisibility. This is the kind of drift X-58 caught after the
    /draft-X family landed: 8 services existed but planner only
    knew about ~17 of them.
    """

    def test_every_registered_service_appears_in_planner_prompt(self):
        from planner import PLANNER_SYSTEM_PROMPT
        from services import REPORT_SERVICES

        missing: list[str] = []
        for slug, svc in REPORT_SERVICES.items():
            tool_name = svc.chat_tool_name
            if tool_name and tool_name not in PLANNER_SYSTEM_PROMPT:
                missing.append(f"{slug} → {tool_name}")
        assert not missing, (
            "Planner system prompt is out of sync with REPORT_SERVICES. "
            "These chat_tool_names are missing from PLANNER_SYSTEM_PROMPT "
            f"and the planner can't propose them: {missing}"
        )
