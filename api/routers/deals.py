"""Deal / transaction endpoints — HTTP contract only; SQL + visibility in services/crm/deals."""

from urllib.parse import unquote

from auth import get_current_user, public_api
from crm_store import LIKE_ESCAPE, like_contains
from fastapi import APIRouter, Depends, HTTPException, Query
from services.crm import deals as deals_service
from services.crm.list_view import PaginatedResponse, list_table_view

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
@public_api
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
    return list_table_view(
        "交易",
        where=where,
        params=tuple(params),
        sort=sort,
        order=order,
        sort_allowlist={
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
        },
        default_sort="宣布日期",
        page=page,
        page_size=page_size,
        user=user,
    )


@router.get("/{name}")
@public_api
def get_deal(name: str, user: dict = Depends(get_current_user)):
    row = deals_service.fetch_deal(unquote(name), user)
    if row is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    return row
