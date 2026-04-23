"""Company endpoints — field visibility enforced by field_policy."""

from urllib.parse import unquote

from auth import get_current_user
from crm_store import LIKE_ESCAPE, like_contains, paginate, query, query_one
from fastapi import APIRouter, Depends, HTTPException, Query
from field_policy import strip_hidden

router = APIRouter()


@router.get("")
def list_companies(
    q: str = Query("", description="Search company name"),
    country: str = Query("", description="Filter by country"),
    type: str = Query("", description="Filter by company type"),
    priority: str = Query("", description="Filter by BD priority"),
    tracked: str = Query("", description="Filter by tracking status"),
    sort: str = Query("客户名称", description="Sort column"),
    order: str = Query("asc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    conditions = []
    params: list = []

    if q:
        conditions.append(
            f'("客户名称" LIKE ? {LIKE_ESCAPE} OR "英文名" LIKE ? {LIKE_ESCAPE} OR "中文名" LIKE ? {LIKE_ESCAPE})'
        )
        params.extend([like_contains(q)] * 3)
    if country:
        conditions.append('"所处国家" = ?')
        params.append(country)
    if type:
        conditions.append('"客户类型" = ?')
        params.append(type)
    if priority:
        conditions.append('"BD跟进优先级" = ?')
        params.append(priority)
    if tracked:
        conditions.append('"追踪状态" = ?')
        params.append(tracked)

    where = " AND ".join(conditions) if conditions else ""
    allowed_sorts = {
        "客户名称",
        "所处国家",
        "客户类型",
        "公司质量评分",
        "BD跟进优先级",
        "核心产品的阶段",
        "市值/估值",
        "追踪状态",
    }
    sort_col = sort if sort in allowed_sorts else "客户名称"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    result = paginate(
        "公司",
        where=where,
        params=tuple(params),
        order_by=f'"{sort_col}" {order_dir}',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "公司", user)
    return result


@router.get("/{name}")
def get_company(name: str, user: dict = Depends(get_current_user)):
    name = unquote(name)
    row = query_one('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))
    if not row:
        raise HTTPException(status_code=404, detail="Company not found")
    return strip_hidden(row, "公司", user)


@router.get("/{name}/assets")
def get_company_assets(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    name = unquote(name)
    result = paginate(
        "资产",
        where='"所属客户" = ?',
        params=(name,),
        order_by='"临床阶段" ASC',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "资产", user)
    return result


@router.get("/{name}/trials")
def get_company_trials(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    name = unquote(name)
    result = paginate(
        "临床",
        where='"公司名称" = ?',
        params=(name,),
        order_by='"数据状态" ASC',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "临床", user)
    return result


@router.get("/{name}/deals")
def get_company_deals(name: str, user: dict = Depends(get_current_user)):
    name = unquote(name)
    rows = query(
        'SELECT * FROM "交易" WHERE "买方公司" = ? OR "卖方/合作方" = ? ORDER BY "宣布日期" DESC',
        (name, name),
    )
    return strip_hidden(rows, "交易", user)
