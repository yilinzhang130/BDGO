"""MNC Buyer Profile endpoints."""

from fastapi import APIRouter, HTTPException, Query
from urllib.parse import unquote
from crm_store import paginate, query_one

router = APIRouter()


@router.get("")
def list_buyers(
    q: str = Query("", description="Search company name"),
    sort: str = Query("company_name", description="Sort column"),
    order: str = Query("asc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    conditions = []
    params: list = []

    if q:
        conditions.append('("company_name" LIKE ? OR "company_cn" LIKE ? OR "heritage_ta" LIKE ?)')
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    where = " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"company_name", "heritage_ta", "annual_revenue", "last_updated", "risk_appetite", "deal_size_preference"}
    sort_col = sort if sort in allowed_sorts else "company_name"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    return paginate(
        "MNC画像",
        where=where,
        params=tuple(params),
        order_by=f'"{sort_col}" {order_dir}',
        page=page,
        page_size=page_size,
    )


@router.get("/{name}")
def get_buyer(name: str):
    name = unquote(name)
    row = query_one('SELECT * FROM "MNC画像" WHERE "company_name" = ?', (name,))
    if not row:
        raise HTTPException(status_code=404, detail="Buyer profile not found")
    return row
