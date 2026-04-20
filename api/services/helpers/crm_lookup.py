"""Shared CRM readers for report services.

Deal evaluator / teaser / rNPV all need the same "find the asset row, format
the BD-relevant fields as a prompt block" lookup. Keep one copy here."""

from __future__ import annotations

from crm_store import query

_ASSET_KEEP_FIELDS = [
    "资产名称", "所属客户", "靶点", "作用机制(MOA)", "临床阶段", "适应症",
    "差异化分级", "差异化描述", "峰值销售预测", "竞品情况", "知识产权",
]


def asset_crm_block(company_name: str, asset_name: str,
                    *, include_clinical: bool = False) -> str:
    """Return a markdown block of CRM data for the given (company, asset).

    Includes up to 5 linked clinical trials when ``include_clinical`` is set
    (used by the deal evaluator which wants stage/status context)."""
    rows = query(
        'SELECT * FROM "资产" WHERE ("资产名称" = ? OR "资产名称" LIKE ?) '
        'AND ("所属客户" = ? OR "所属客户" LIKE ?) LIMIT 1',
        (asset_name, f"%{asset_name}%", company_name, f"%{company_name}%"),
    )
    lines: list[str] = []
    if rows:
        row = rows[0]
        for k in _ASSET_KEEP_FIELDS:
            v = row.get(k)
            if v:
                lines.append(f"- **{k}**: {v}")

    if include_clinical:
        clin = query(
            'SELECT * FROM "临床" WHERE "资产名称" LIKE ? OR "研究产品" LIKE ? LIMIT 5',
            (f"%{asset_name}%", f"%{asset_name}%"),
        )
        if clin:
            lines.append("\n**相关临床试验**：")
            for c in clin:
                name = c.get("研究名称") or c.get("NCT号") or ""
                phase = c.get("临床阶段") or ""
                status = c.get("状态") or ""
                lines.append(f"- {name} | {phase} | {status}")

    return "\n".join(lines) or "(CRM 无匹配资产记录)"
