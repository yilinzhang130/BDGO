"""Clinical trial endpoints."""

from auth import get_current_user, public_api
from crm_store import LIKE_ESCAPE, like_contains, query_one
from fastapi import APIRouter, Depends, HTTPException, Query
from field_policy import strip_hidden
from services.crm.list_view import list_table_view

router = APIRouter()


@router.get("")
@public_api
def list_clinical(
    q: str = Query("", description="Search trial/asset/company"),
    company: str = Query(""),
    asset: str = Query(""),
    phase: str = Query("", description="Filter by phase"),
    status: str = Query("", description="Filter by data status"),
    result: str = Query("", description="Filter by result"),
    sort: str = Query("试验ID"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    conditions = []
    params: list = []

    if q:
        conditions.append(
            f'("试验ID" LIKE ? {LIKE_ESCAPE} OR "资产名称" LIKE ? {LIKE_ESCAPE} OR "公司名称" LIKE ? {LIKE_ESCAPE} OR "适应症" LIKE ? {LIKE_ESCAPE})'
        )
        params.extend([like_contains(q)] * 4)
    if company:
        conditions.append('"公司名称" = ?')
        params.append(company)
    if asset:
        conditions.append('"资产名称" = ?')
        params.append(asset)
    if phase:
        conditions.append('"临床期次" = ?')
        params.append(phase)
    if status:
        conditions.append('"数据状态" = ?')
        params.append(status)
    if result:
        conditions.append('"结果判定" = ?')
        params.append(result)

    where = " AND ".join(conditions) if conditions else ""
    return list_table_view(
        "临床",
        where=where,
        params=tuple(params),
        sort=sort,
        order=order,
        sort_allowlist={
            "试验ID",
            "资产名称",
            "公司名称",
            "临床期次",
            "数据状态",
            "结果判定",
            "适应症",
            "主要终点名称",
            "主要终点结果值",
            "安全性标志",
        },
        default_sort="试验ID",
        page=page,
        page_size=page_size,
        user=user,
    )


@router.get("/{record_id}")
@public_api
def get_clinical_record(record_id: str, user: dict = Depends(get_current_user)):
    row = query_one('SELECT * FROM "临床" WHERE "记录ID" = ?', (record_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Clinical record not found")
    return strip_hidden(row, "临床", user)
