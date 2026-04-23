"""Deal / transaction endpoints."""

from urllib.parse import unquote

from auth import get_current_user
from crm_store import LIKE_ESCAPE, like_contains, paginate, query_one
from fastapi import APIRouter, Depends, HTTPException, Query
from field_policy import strip_hidden

router = APIRouter()


@router.get("")
def list_deals(
    q: str = Query("", description="Search deal name/company/asset"),
    type: str = Query("", description="Filter by deal type"),
    buyer: str = Query(""),
    seller: str = Query(""),
    sort: str = Query("宣布日期"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    conditions = []
    params: list = []

    if q:
        conditions.append(
            f'("交易名称" LIKE ? {LIKE_ESCAPE} OR "买方公司" LIKE ? {LIKE_ESCAPE} OR "卖方/合作方" LIKE ? {LIKE_ESCAPE} OR "资产名称" LIKE ? {LIKE_ESCAPE})'
        )
        params.extend([like_contains(q)] * 4)
    if type:
        conditions.append('"交易类型" = ?')
        params.append(type)
    if buyer:
        conditions.append(f'"买方公司" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(buyer))
    if seller:
        conditions.append(f'"卖方/合作方" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(seller))

    where = " AND ".join(conditions) if conditions else ""
    allowed_sorts = {
        "交易名称",
        "交易类型",
        "买方公司",
        "卖方/合作方",
        "交易总额($M)",
        "宣布日期",
        "战略评分",
        "资产名称",
        "靶点",
        "临床阶段",
        "首付款($M)",
    }
    sort_col = sort if sort in allowed_sorts else "宣布日期"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    result = paginate(
        "交易",
        where=where,
        params=tuple(params),
        order_by=f'"{sort_col}" {order_dir}',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "交易", user)
    return result


@router.get("/{name}")
def get_deal(name: str, user: dict = Depends(get_current_user)):
    name = unquote(name)
    row = query_one('SELECT * FROM "交易" WHERE "交易名称" = ?', (name,))
    if not row:
        raise HTTPException(status_code=404, detail="Deal not found")
    return strip_hidden(row, "交易", user)
