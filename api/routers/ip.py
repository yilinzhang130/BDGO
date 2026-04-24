"""IP/Patent endpoints — HTTP contract only; SQL in services/crm/ip."""

from urllib.parse import unquote

from crm_store import LIKE_ESCAPE, like_contains
from fastapi import APIRouter, HTTPException, Query
from services.crm import ip as ip_service
from services.crm.list_view import PaginatedResponse, list_table_view

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_ip(
    q: str = Query("", description="Search patent/company/asset"),
    company: str = Query(""),
    asset: str = Query(""),
    status: str = Query("", description="Filter by status"),
    jurisdiction: str = Query(""),
    sort: str = Query("到期日"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    conditions = []
    params: list = []

    if q:
        conditions.append(
            f'("专利号" LIKE ? {LIKE_ESCAPE} OR "关联公司" LIKE ? {LIKE_ESCAPE} OR "关联资产" LIKE ? {LIKE_ESCAPE} OR "专利持有人" LIKE ? {LIKE_ESCAPE})'
        )
        params.extend([like_contains(q)] * 4)
    if company:
        conditions.append(f'"关联公司" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(company))
    if asset:
        conditions.append(f'"关联资产" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(asset))
    if status:
        conditions.append('"状态" = ?')
        params.append(status)
    if jurisdiction:
        conditions.append('"管辖区" = ?')
        params.append(jurisdiction)

    where = " AND ".join(conditions) if conditions else ""
    return list_table_view(
        "IP",
        where=where,
        params=tuple(params),
        sort=sort,
        order=order,
        sort_allowlist={
            "专利号",
            "关联公司",
            "关联资产",
            "到期日",
            "状态",
            "管辖区",
            "专利持有人",
            "专利类型",
        },
        default_sort="到期日",
        page=page,
        page_size=page_size,
    )


@router.get("/{patent_number}")
def get_patent(patent_number: str):
    row = ip_service.fetch_patent(unquote(patent_number))
    if row is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    return row
