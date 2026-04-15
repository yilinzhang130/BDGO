"""
field_policy.py — Per-table field visibility rules.

Fields listed in HIDDEN_FIELDS are stripped from API responses for
non-admin users. Admins (is_admin=True) always see everything.

To add or remove a hidden field, edit the sets below and redeploy.
"""

from __future__ import annotations

# Map table name → set of column names to hide from non-admin users
HIDDEN_FIELDS: dict[str, set[str]] = {
    "公司": {
        "BD跟进优先级",
        "BD联系人",
        "BD状态",
        "内部备注",
        "内部评分",
        "追踪状态",
        "跟进记录",
    },
    "资产": {
        "BD状态",
        "内部评分",
        "内部备注",
        "追踪状态",
        "跟进记录",
    },
    "交易": {
        "内部备注",
        "BD状态",
        "BD跟进优先级",
    },
    "临床": set(),
    "IP": set(),
    "MNC画像": set(),
}


def strip_hidden(rows: list[dict] | dict, table: str, is_admin: bool) -> list[dict] | dict:
    """Remove hidden fields from one row (dict) or a list of rows.

    If is_admin is True, rows are returned unchanged.
    """
    if is_admin:
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
