"""Global cross-table search endpoint — with Chinese bigram fuzzy matching."""

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
    ("clinical", "临床",
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


def _build_patterns(q: str) -> list[str]:
    """Return a list of LIKE patterns for fuzzy matching.

    Strategy:
    1. Always include the full query as one pattern (exact substring).
    2. For queries ≥ 3 chars, generate 2-char bigrams so that e.g. "时迈生物"
       also matches "时迈药业" via the "时迈" bigram.

    We de-duplicate and keep unique patterns.
    """
    q = q.strip()
    patterns: list[str] = [f"%{q}%"]  # full match first

    if len(q) >= 3:
        seen: set[str] = {q}
        for i in range(len(q) - 1):
            bigram = q[i : i + 2]
            if bigram not in seen:
                seen.add(bigram)
                patterns.append(f"%{bigram}%")

    return patterns


@router.get("/global")
def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(5, ge=1, le=10, description="Max results per category"),
):
    """Search across all CRM tables simultaneously.

    Uses bigram patterns to handle fuzzy Chinese company-name matching,
    e.g. "时迈生物" will also surface "时迈药业".
    """
    results: dict = {}
    patterns = _build_patterns(q)

    for category, table, search_cols, display_cols, pk_col, link_tpl in _SEARCH_TABLES:
        # Build OR clause: for each (column, pattern) combination
        all_cols = list(dict.fromkeys(display_cols + [pk_col] + search_cols[:1]))
        select = ", ".join(f'"{c}"' for c in all_cols)

        # For each search column, OR all patterns together
        col_clauses = []
        params: list = []
        for col in search_cols:
            for pat in patterns:
                col_clauses.append(f'"{col}" LIKE ?')
                params.append(pat)

        where = " OR ".join(col_clauses)
        params.append(limit)

        rows = query(
            f'SELECT {select} FROM "{table}" WHERE {where} LIMIT ?',
            tuple(params),
        )

        if rows:
            # Deduplicate by pk_col (bigrams can return same row multiple times)
            seen_pks: set = set()
            items = []
            for row in rows:
                pk_val = row.get(pk_col)
                if pk_val in seen_pks:
                    continue
                seen_pks.add(pk_val)

                link = link_tpl
                for col in all_cols:
                    link = link.replace("{" + col + "}", str(row.get(col, "") or ""))
                items.append({
                    "display": {c: row.get(c, "") for c in display_cols},
                    "link": link,
                })
            if items:
                results[category] = items[:limit]

    return {"query": q, "results": results}
