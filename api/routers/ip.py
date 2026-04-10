"""IP/Patent endpoints."""

from fastapi import APIRouter, HTTPException, Query
from urllib.parse import unquote
from db import paginate, query_one

router = APIRouter()


@router.get("")
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
        conditions.append('("专利号" LIKE ? OR "关联公司" LIKE ? OR "关联资产" LIKE ? OR "专利持有人" LIKE ?)')
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if company:
        conditions.append('"关联公司" LIKE ?')
        params.append(f"%{company}%")
    if asset:
        conditions.append('"关联资产" LIKE ?')
        params.append(f"%{asset}%")
    if status:
        conditions.append('"状态" = ?')
        params.append(status)
    if jurisdiction:
        conditions.append('"管辖区" = ?')
        params.append(jurisdiction)

    where = " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"专利号", "关联公司", "关联资产", "到期日", "状态", "管辖区", "专利持有人", "专利类型"}
    sort_col = sort if sort in allowed_sorts else "到期日"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    return paginate(
        "IP",
        where=where,
        params=tuple(params),
        order_by=f'"{sort_col}" {order_dir}',
        page=page,
        page_size=page_size,
    )


@router.get("/{patent_number}")
def get_patent(patent_number: str):
    patent_number = unquote(patent_number)
    row = query_one('SELECT * FROM "IP" WHERE "专利号" = ?', (patent_number,))
    if not row:
        raise HTTPException(status_code=404, detail="Patent not found")
    return row
