"""Comprehensive chip-routing audit across every report service.

Generalizes the earlier per-service drift checks (#119, #121, #122) into
one parametrized scan: walk every ``api/services/reports/*.py`` file via
AST, find every dict literal that looks like a chip
(``{"label": ..., "command": ..., "slug": ...}``), and assert no chip
violates the closed-loop rule:

    A chip with a "Draft X" / "起草 X" label MUST NOT route to
    slug="legal-review" — /legal is review-mode, requires contract_text
    the user doesn't have when they're trying to draft something.

Background:
  This bug shipped four times before we caught it everywhere
  (#119, #121, #122). The shared root cause: chip labels are written
  for the user ("Draft License Agreement"), but the underlying command
  was wired to /legal review. AST audit catches it at test time so
  PR-5 of the same bug doesn't ship.

Why AST not regex:
  Chip dicts can span multiple lines, use string concatenation for the
  command, or wrap label/slug in different orders. AST gives us the
  literal value of each constant string assignment regardless of
  formatting.

Why label-based not slug-based:
  /legal review IS the right destination for a "Review TS Risks" chip.
  The bug is specifically when the chip *promises* drafting in its
  label but lands the user in review mode. We check the label.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPORTS_DIR = Path(__file__).parent.parent.parent.parent / "services" / "reports"
SERVICE_FILES = sorted(p for p in REPORTS_DIR.glob("*.py") if p.name != "__init__.py")


def _extract_chips(tree: ast.AST) -> list[dict]:
    """Walk the AST and return every dict literal that looks like a chip.

    A "chip" here is a dict literal containing string-typed keys
    ``label``, ``command``, and ``slug`` — that's the universal shape
    used across every service's _build_suggested_commands.
    """
    chips: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        d: dict = {}
        for key_node, val_node in zip(node.keys, node.values, strict=False):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            d[key_node.value] = val_node
        if not {"label", "command", "slug"}.issubset(d.keys()):
            continue

        # Resolve label and slug to their string literal values when possible.
        # command may be a Call (str.join) or a complex BinOp f-string — we
        # only need label + slug for the audit rule, which are always
        # constant strings in practice.
        label_val = _const_str(d["label"])
        slug_val = _const_str(d["slug"])
        if label_val is None or slug_val is None:
            continue
        chips.append(
            {
                "label": label_val,
                "slug": slug_val,
                "lineno": node.lineno,
            }
        )
    return chips


def _const_str(node: ast.expr) -> str | None:
    """Return the literal string value of an AST node, or None if it's
    not a plain string constant (e.g. an f-string with interpolations)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Joined string with no interpolations: ast.JoinedStr containing only
    # FormattedValue/Constant — for our purpose, treat as opaque.
    return None


_DRAFTING_LABEL_KEYWORDS = ("draft", "起草", "draft-", "撰写", "拟订")


def _label_implies_drafting(label: str) -> bool:
    """True if the chip label promises the user a drafting action."""
    low = label.lower()
    if "review" in low or "审查" in low or "审阅" in low or "复盘" in low:
        # "Review X Risks" / "Review X Draft" — explicitly review-mode,
        # /legal is correct.
        return False
    return any(kw in low for kw in _DRAFTING_LABEL_KEYWORDS)


# ─────────────────────────────────────────────────────────────
# Discovery: every file produces a list of chips. Tests are
# parametrized over every (service_file, chip) pair so a failure
# names the exact file + chip that violated the rule.
# ─────────────────────────────────────────────────────────────


def _all_chips() -> list[tuple[str, dict, str]]:
    """Returns [(service_file_name, chip_dict, error_msg_prefix), ...]."""
    out: list[tuple[str, dict, str]] = []
    for path in SERVICE_FILES:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path.name)
        for chip in _extract_chips(tree):
            out.append((path.name, chip, f"{path.name}:{chip['lineno']}"))
    return out


_ALL_CHIPS = _all_chips()


def test_audit_found_chips_at_all():
    """Sanity: the AST walker actually finds chips. If this fails, the
    extractor is broken and other tests would silently false-pass."""
    assert len(_ALL_CHIPS) > 0, "Chip extraction returned 0 chips — extractor broken?"
    # We have at least one chip per /draft-X service + several others
    files_with_chips = {p[0] for p in _ALL_CHIPS}
    assert len(files_with_chips) >= 8


@pytest.mark.parametrize(
    ("service_file", "chip", "msg_prefix"),
    _ALL_CHIPS,
    ids=lambda x: x if isinstance(x, str) else "",
)
def test_no_drafting_label_routes_to_legal_review(service_file, chip, msg_prefix):
    """The closed-loop bug: chip labels promising "Draft X" must not
    route to slug="legal-review". /legal review needs contract_text the
    user doesn't have when they're starting to draft.

    Legitimate /legal chips ALL use "Review" wording (e.g. "Review SPA
    Risks") because that's what /legal actually does. If you're tempted
    to add a "Draft X" chip routing to legal-review, you want a
    /draft-X service instead.
    """
    if chip["slug"] != "legal-review":
        return  # Not a /legal chip; nothing to audit
    assert not _label_implies_drafting(chip["label"]), (
        f"{msg_prefix}: chip label {chip['label']!r} promises drafting but routes to "
        f'slug="legal-review" (review-mode). /legal requires contract_text or '
        f"source_task_id; a freshly-clicked drafting chip has neither. Either:\n"
        f"  1. Change the slug to a /draft-X service (e.g. draft-license, draft-ts),\n"
        f'  2. Or change the label to "Review X Risks" if the user already has the '
        f"contract text to review."
    )


def test_audit_does_not_blanket_ban_legal_review_chips():
    """Sanity: /legal review chips with "Review X" labels are fine and
    should still exist (they're the legitimate use case)."""
    review_chips = [c for _, c, _ in _ALL_CHIPS if c["slug"] == "legal-review"]
    review_labeled = [c for c in review_chips if "review" in c["label"].lower()]
    assert len(review_labeled) > 0, (
        "Expected at least one 'Review X' chip routing to /legal — those are the "
        "legitimate post-draft handoffs from /draft-X services. If this fails, "
        "the audit might have over-corrected and removed all /legal chip handoffs."
    )
