"""Deal / transaction endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from urllib.parse import unquote
from crm_store import paginate, query_one
from auth import get_current_user
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
        conditions.append('("交易名称" LIKE ? OR "买方公司" LIKE ? OR "卖方/合作方" LIKE ? OR "资产名称" LIKE ?)')
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if type:
        conditions.append('"交易类型" = ?')
        params.append(type)
    if buyer:
        conditions.append('"买方公司" LIKE ?')
        params.append(f"%{buyer}%")
    if seller:
        conditions.append('"卖方/合作方" LIKE ?')
        params.append(f"%{seller}%")

    where = " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"交易名称", "交易类型", "买方公司", "卖方/合作方", "交易总额($M)", "宣布日期", "战略评分", "资产名称", "靶点", "临床阶段", "首付款($M)"}
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
