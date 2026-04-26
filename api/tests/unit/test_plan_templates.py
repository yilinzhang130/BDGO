"""Tests for plan_templates module (X-18)."""

from __future__ import annotations

import plan_templates as pt

# ─────────────────────────────────────────────────────────────
# Built-in template presence
# ─────────────────────────────────────────────────────────────


def test_builtin_slugs_present():
    slugs = list(pt.BUILTIN_TEMPLATES.keys())
    assert "bd-intake" in slugs
    assert "mnc-analysis" in slugs
    assert "deal-eval" in slugs
    assert "outreach-campaign" in slugs
    assert "contract-review" in slugs


def test_list_builtins_returns_all():
    items = pt.list_builtins()
    assert len(items) == len(pt.BUILTIN_TEMPLATES)
    for item in items:
        assert "title" in item
        assert "steps" in item
        assert isinstance(item["steps"], list)
        assert len(item["steps"]) > 0


def test_get_builtin_known():
    t = pt.get_builtin("bd-intake")
    assert t is not None
    assert t["title"] == "BD Intake — 资产入栈全流程"
    assert len(t["steps"]) == 7


def test_get_builtin_unknown_returns_none():
    assert pt.get_builtin("does-not-exist") is None


def test_get_builtin_returns_copy():
    t1 = pt.get_builtin("bd-intake")
    t2 = pt.get_builtin("bd-intake")
    assert t1 is not t2  # independent copies


# ─────────────────────────────────────────────────────────────
# BD Intake template structure
# ─────────────────────────────────────────────────────────────


def test_bd_intake_required_steps():
    t = pt.get_builtin("bd-intake")
    steps = t["steps"]
    required_ids = {s["id"] for s in steps if s["required"]}
    # s4 (deal evaluation) and s7 (synthesize) must be required
    assert "s4" in required_ids
    assert "s7" in required_ids


def test_bd_intake_default_selected():
    t = pt.get_builtin("bd-intake")
    steps = t["steps"]
    # s3 (IP) and s6 (timing) should be default_selected=False
    s3 = next(s for s in steps if s["id"] == "s3")
    s6 = next(s for s in steps if s["id"] == "s6")
    assert s3["default_selected"] is False
    assert s6["default_selected"] is False


def test_bd_intake_all_steps_have_required_keys():
    t = pt.get_builtin("bd-intake")
    required_keys = {
        "id",
        "title",
        "description",
        "tools_expected",
        "required",
        "default_selected",
        "estimated_seconds",
    }
    for step in t["steps"]:
        missing = required_keys - set(step.keys())
        assert not missing, f"Step {step.get('id')} missing keys: {missing}"


def test_all_templates_have_required_keys():
    required_template_keys = {"plan_id", "title", "summary", "steps", "builtin", "slug"}
    for slug, t in pt.BUILTIN_TEMPLATES.items():
        missing = required_template_keys - set(t.keys())
        assert not missing, f"Template {slug} missing keys: {missing}"


# ─────────────────────────────────────────────────────────────
# resolve_template — built-in lookup
# ─────────────────────────────────────────────────────────────


def test_resolve_template_builtin_no_user():
    resolved = pt.resolve_template(None, "bd-intake")
    assert resolved is not None
    assert resolved["plan_id"] == "builtin:bd-intake"


def test_resolve_template_builtin_with_user():
    resolved = pt.resolve_template("user-123", "bd-intake")
    assert resolved is not None


def test_resolve_template_unknown_no_user():
    resolved = pt.resolve_template(None, "does-not-exist")
    assert resolved is None


# ─────────────────────────────────────────────────────────────
# outreach-campaign template
# ─────────────────────────────────────────────────────────────


def test_outreach_campaign_has_batch_outreach():
    t = pt.get_builtin("outreach-campaign")
    all_tools = [tool for step in t["steps"] for tool in step["tools_expected"]]
    assert "batch_outreach_email" in all_tools


# ─────────────────────────────────────────────────────────────
# Estimated seconds are positive integers
# ─────────────────────────────────────────────────────────────


def test_estimated_seconds_positive():
    for slug, t in pt.BUILTIN_TEMPLATES.items():
        for step in t["steps"]:
            assert isinstance(step["estimated_seconds"], int), (
                f"Template {slug} step {step['id']}: estimated_seconds should be int"
            )
            assert step["estimated_seconds"] > 0, (
                f"Template {slug} step {step['id']}: estimated_seconds should be > 0"
            )
