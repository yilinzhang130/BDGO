"""Asset endpoints — field visibility enforced by field_policy."""

from fastapi import APIRouter, Depends, HTTPException, Query
from urllib.parse import unquote
from crm_store import paginate, query_one
from auth import get_current_user
from field_policy import strip_hidden, is_admin_user

router = APIRouter()


@router.get("")
def list_assets(
    q: str = Query("", description="Search asset name"),
    company: str = Query("", description="Filter by company"),
    phase: str = Query("", description="Filter by clinical phase"),
    disease: str = Query("", description="Filter by disease area"),
    target: str = Query("", description="Filter by target"),
    scored: str = Query("", description="yes = only assets with Q scores"),
    tracked: str = Query("", description="Filter by tracking status"),
    sort: str = Query("资产名称", description="Sort column"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    conditions = []
    params: list = []

    if q:
        conditions.append('("资产名称" LIKE ? OR "资产代号" LIKE ? OR "靶点" LIKE ?)')
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if company:
        conditions.append('"所属客户" = ?')
        params.append(company)
    if phase:
        conditions.append('"临床阶段" = ?')
        params.append(phase)
    if disease:
        conditions.append('"疾病领域" = ?')
        params.append(disease)
    if target:
        conditions.append('"靶点" LIKE ?')
        params.append(f"%{target}%")
    if tracked:
        conditions.append('"追踪状态" = ?')
        params.append(tracked)
    if scored == "yes":
        conditions.append('''(
            ("Q1_生物学" IS NOT NULL AND "Q1_生物学" != '')
            OR ("Q2_药物形式" IS NOT NULL AND "Q2_药物形式" != '')
            OR ("Q3_临床监管" IS NOT NULL AND "Q3_临床监管" != '')
            OR ("Q4_商业交易性" IS NOT NULL AND "Q4_商业交易性" != '')
        )''')

    where = " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"资产名称", "所属客户", "临床阶段", "疾病领域", "靶点", "BD优先级", "技术平台类别", "作用机制(MOA)"}
    sort_col = sort if sort in allowed_sorts else "资产名称"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    result = paginate(
        "资产",
        where=where,
        params=tuple(params),
        order_by=f'"{sort_col}" {order_dir}',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "资产", user)
    return result


@router.get("/{company}/{name}")
def get_asset(company: str, name: str, user: dict = Depends(get_current_user)):
    company = unquote(company)
    name = unquote(name)
    row = query_one(
        'SELECT * FROM "资产" WHERE "资产名称" = ? AND "所属客户" = ?',
        (name, company),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    return strip_hidden(row, "资产", user)


@router.get("/{company}/{name}/trials")
def get_asset_trials(
    company: str,
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    company = unquote(company)
    name = unquote(name)
    result = paginate(
        "临床",
        where='"资产名称" = ? AND "公司名称" = ?',
        params=(name, company),
        order_by='"临床期次" ASC',
        page=page,
        page_size=page_size,
    )
    result["data"] = strip_hidden(result["data"], "临床", user)
    return result
