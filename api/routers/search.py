"""Global cross-table search endpoint."""

from fastapi import APIRouter, Query
from db import query

router = APIRouter()

# (category, physical_table, search_cols, display_cols, pk_col, link_template)
_SEARCH_TABLES = [
    ("companies", "公司",
     ["客户名称", "英文名", "中文名"],
     ["客户名称", "客户类型", "所处国家"],
     "客户名称", "/companies/{客户名称}"),
    ("assets", "资产",
     ["文本", "资产代号", "靶点"],
     ["文本", "所属客户", "临床阶段"],
     "文本", "/assets/{所属客户}/{文本}"),
    ("clinical", "临床_v3",
     ["试验ID", "资产名称", "公司名称", "适应症"],
     ["试验ID", "资产名称", "临床期次"],
     "记录ID", "/clinical/{记录ID}"),
    ("deals", "交易",
     ["交易名称", "买方公司", "卖方/合作方", "资产名称"],
     ["交易名称", "交易类型", "宣布日期"],
     "交易名称", "/deals/{交易名称}"),
    ("ip", "IP",
     ["专利号", "关联公司", "关联资产"],
     ["专利号", "关联公司", "状态"],
     "专利号", "/ip/{专利号}"),
]


@router.get("/global")
def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(5, ge=1, le=10, description="Max results per category"),
):
    """Search across all CRM tables simultaneously."""
    results: dict = {}
    pattern = f"%{q}%"

    for category, table, search_cols, display_cols, pk_col, link_tpl in _SEARCH_TABLES:
        where = " OR ".join(f'"{c}" LIKE ?' for c in search_cols)
        # Select display cols + pk col (for link building)
        all_cols = list(set(display_cols + [pk_col] + search_cols[:1]))
        select = ", ".join(f'"{c}"' for c in all_cols)

        rows = query(
            f'SELECT {select} FROM "{table}" WHERE {where} LIMIT ?',
            tuple([pattern] * len(search_cols) + [limit]),
        )

        if rows:
            items = []
            for row in rows:
                # Build link by substituting column values into template
                link = link_tpl
                for col in all_cols:
                    link = link.replace("{" + col + "}", str(row.get(col, "") or ""))
                items.append({
                    "display": {c: row.get(c, "") for c in display_cols},
                    "link": link,
                })
            results[category] = items

    return {"query": q, "results": results}
