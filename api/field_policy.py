"""
field_policy.py — Per-table field visibility rules.

Three visibility tiers:
  - **Admin** — sees all fields + can edit
  - **Internal** (employees of the owning company) — sees all fields read-only
  - **External** (partners / prospects) — subjective/BD fields stripped

Fields listed in HIDDEN_FIELDS are stripped from API responses for
**external** users only. Admins and internal users see everything.

To add or remove a hidden field, edit the sets below and redeploy.
"""

from __future__ import annotations

# Map table name → set of column names to hide from external users.
# Grouped by category so it's easy to see why each field is hidden.
HIDDEN_FIELDS: dict[str, set[str]] = {
    "公司": {
        # — Business ops (CRM state) —
        "BD跟进优先级",
        "BD联系人",
        "BD状态",
        "BD来源",
        "推荐交易类型",
        "跟进建议",
        "跟进记录",
        "潜在买方",
        "联系人",
        "追踪状态",
        # — Subjective evaluations —
        "POS预测",
        "公司质量评分",
        "内部评分",
        # — Internal workflow/notes —
        "内部备注",
        "备注",
        "分析的日期",
        "BP来源",
    },
    "资产": {
        # — Business ops —
        "BD优先级",
        "BD类别",
        "BD状态",
        "是否核心资产",
        "追踪状态",
        "合作方",
        # — Subjective evaluations (Q1–Q4 analyst scoring) —
        "POS预测",
        "峰值销售预测",
        "Q1_生物学",
        "Q2_药物形式",
        "Q3_临床监管",
        "Q4_商业交易性",
        "Q总分",
        "差异化分级",
        "差异化描述",
        "风险因素",
        "内部评分",
        # — Internal workflow/notes —
        "内部备注",
        "跟进记录",
        "BP来源",
        "待查论文",
        "_enrich_confidence",
        "_enrich_date",
    },
    "交易": {
        "BD状态",
        "BD跟进优先级",
        "内部备注",
        "战略解读",
    },
    "临床": {
        # Mostly objective trial facts are fine for external.
        # Only hide internal assessment fields.
        "临床评分",
        "评估摘要",
        "内部备注",
    },
}


def can_see_internal_fields(user: dict | None) -> bool:
    """External users never see HIDDEN_FIELDS. Internal + admin do."""
    if not user:
        return False
    return bool(user.get("is_admin") or user.get("is_internal"))


def strip_hidden(
    rows: list[dict] | dict,
    table: str,
    user_or_flag: dict | bool | None,
) -> list[dict] | dict:
    """Remove hidden fields from one row or a list of rows.

    *user_or_flag* can be:
      - a user dict (recommended) — checks is_admin OR is_internal
      - a bool — legacy path (True = show everything)
      - None — treat as external user
    """
    if isinstance(user_or_flag, bool):
        show_all = user_or_flag
    else:
        show_all = can_see_internal_fields(user_or_flag)

    if show_all:
        return rows

    hidden = HIDDEN_FIELDS.get(table, set())
    if not hidden:
        return rows

    def _strip(row: dict) -> dict:
        return {k: v for k, v in row.items() if k not in hidden}

    if isinstance(rows, list):
        return [_strip(r) for r in rows]
    return _strip(rows)


def is_admin_user(user: dict | None) -> bool:
    """Return True if the given user dict has is_admin=True."""
    if not user:
        return False
    return bool(user.get("is_admin"))
