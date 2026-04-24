"""Stats / dashboard aggregation endpoints."""

from crm_store import parse_numeric, query, query_one
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# ── Response models ─────────────────────────────────────────────
# Mirror the frontend types in frontend/src/lib/api.ts. Keep them
# narrow (only the fields the dashboard reads); new fields added to
# the SQL SELECT should land in the response model deliberately.


class OverviewStats(BaseModel):
    companies: int
    assets: int
    clinical_records: int
    active_trials: int
    deals: int
    tracked_companies: int


class CountryCount(BaseModel):
    country: str
    count: int


class CompanyTypeCount(BaseModel):
    type: str
    count: int


class PhaseCount(BaseModel):
    phase: str
    count: int


class IndicationCount(BaseModel):
    indication: str
    count: int


class DealTypeCount(BaseModel):
    type: str
    count: int


class DealTimelinePoint(BaseModel):
    month: str
    count: int
    total_value: float


class TargetCount(BaseModel):
    target: str
    count: int


@router.get("/overview", response_model=OverviewStats)
def overview():
    row = query_one("""
        SELECT
            (SELECT COUNT(*) FROM "公司") AS companies,
            (SELECT COUNT(*) FROM "资产") AS assets,
            (SELECT COUNT(*) FROM "临床") AS clinical_records,
            (SELECT COUNT(*) FROM "临床" WHERE "数据状态" != '已读出' AND "数据状态" != '') AS active_trials,
            (SELECT COUNT(*) FROM "交易") AS deals,
            (SELECT COUNT(*) FROM "公司" WHERE "追踪状态" = '追踪中') AS tracked_companies
    """)
    return row


@router.get("/companies-by-country", response_model=list[CountryCount])
def companies_by_country():
    rows = query("""
        SELECT COALESCE(NULLIF("所处国家", ''), 'Unknown') AS country,
               COUNT(*) AS count
        FROM "公司"
        GROUP BY country
        ORDER BY count DESC
        LIMIT 20
    """)
    return rows


@router.get("/companies-by-type", response_model=list[CompanyTypeCount])
def companies_by_type():
    rows = query("""
        SELECT COALESCE(NULLIF("客户类型", ''), 'Unknown') AS type,
               COUNT(*) AS count
        FROM "公司"
        GROUP BY type
        ORDER BY count DESC
    """)
    return rows


@router.get("/pipeline-by-phase", response_model=list[PhaseCount])
def pipeline_by_phase():
    rows = query("""
        SELECT COALESCE(NULLIF("临床阶段", ''), 'Unknown') AS phase,
               COUNT(*) AS count
        FROM "资产"
        GROUP BY phase
        ORDER BY count DESC
    """)
    return rows


@router.get("/indications-top", response_model=list[IndicationCount])
def indications_top():
    rows = query("""
        SELECT COALESCE(NULLIF("疾病领域", ''), 'Unknown') AS indication,
               COUNT(*) AS count
        FROM "资产"
        WHERE "疾病领域" IS NOT NULL AND "疾病领域" != ''
        GROUP BY indication
        ORDER BY count DESC
        LIMIT 25
    """)
    return rows


@router.get("/deals-by-type", response_model=list[DealTypeCount])
def deals_by_type():
    rows = query("""
        SELECT COALESCE(NULLIF("交易类型", ''), 'Unknown') AS type,
               COUNT(*) AS count
        FROM "交易"
        GROUP BY type
        ORDER BY count DESC
    """)
    return rows


@router.get("/deals-timeline", response_model=list[DealTimelinePoint])
def deals_timeline():
    """Deals grouped by year-month."""
    rows = query("""
        SELECT "宣布日期", "交易总额($M)"
        FROM "交易"
        WHERE "宣布日期" IS NOT NULL AND "宣布日期" != ''
        ORDER BY "宣布日期"
    """)
    # Group by YYYY/MM
    timeline: dict[str, dict] = {}
    for r in rows:
        date_str = r.get("宣布日期", "") or ""
        # Handle YYYY/MM/DD or YYYY-MM-DD
        parts = date_str.replace("-", "/").split("/")
        if len(parts) >= 2:
            key = f"{parts[0]}/{parts[1].zfill(2)}"
            if key not in timeline:
                timeline[key] = {"month": key, "count": 0, "total_value": 0}
            timeline[key]["count"] += 1
            val = parse_numeric(r.get("交易总额($M)"))
            if val:
                timeline[key]["total_value"] += val

    return sorted(timeline.values(), key=lambda x: x["month"])


@router.get("/targets-top", response_model=list[TargetCount])
def targets_top():
    rows = query("""
        SELECT COALESCE(NULLIF("靶点", ''), 'Unknown') AS target,
               COUNT(*) AS count
        FROM "资产"
        WHERE "靶点" IS NOT NULL AND "靶点" != ''
        GROUP BY target
        ORDER BY count DESC
        LIMIT 25
    """)
    return rows
