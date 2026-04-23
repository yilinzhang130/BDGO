"""Catalyst calendar endpoints — aggregates catalyst data from 资产 and 临床 tables."""

import re
from datetime import date, datetime

from crm_store import query
from fastapi import APIRouter, Query

router = APIRouter()

# ---------------------------------------------------------------------------
# Date parsing — handles: 2025-06-24, 2026 Q3, 2026 H2, 2025, 2027-06, etc.
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"(20\d{2})")
_Q_RE = re.compile(r"(20\d{2})\s*Q([1-4])", re.IGNORECASE)
_H_RE = re.compile(r"(20\d{2})\s*H([12])", re.IGNORECASE)
_YM_RE = re.compile(r"(20\d{2})-(\d{1,2})")
_YMD_RE = re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})")

_Q_MONTHS = {"1": 3, "2": 6, "3": 9, "4": 12}
_H_MONTHS = {"1": 6, "2": 12}


def _parse_date(raw: str) -> str | None:
    """Parse freeform date text into YYYY-MM-DD (best-effort midpoint)."""
    if not raw or raw.strip() in ("待定", "TBD", "-", "N/A", ""):
        return None
    s = raw.strip()

    # Full date: 2025-06-24
    m = _YMD_RE.search(s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # Year-month: 2027-06
    m = _YM_RE.search(s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-15"

    # Quarter: 2026 Q3
    m = _Q_RE.search(s)
    if m:
        month = _Q_MONTHS[m.group(2)]
        return f"{m.group(1)}-{month:02d}-15"

    # Half: 2026 H2
    m = _H_RE.search(s)
    if m:
        month = _H_MONTHS[m.group(2)]
        return f"{m.group(1)}-{month:02d}-15"

    # Bare year: 2025
    m = _YEAR_RE.search(s)
    if m:
        return f"{m.group(1)}-06-30"

    return None


def _status(parsed_date: str, today: str) -> str:
    """Determine catalyst status: overdue / upcoming / imminent / far."""
    if parsed_date < today:
        return "overdue"
    # Within 90 days
    try:
        d = datetime.strptime(parsed_date, "%Y-%m-%d").date()
        t = datetime.strptime(today, "%Y-%m-%d").date()
        delta = (d - t).days
        if delta <= 30:
            return "imminent"
        if delta <= 90:
            return "upcoming"
        return "far"
    except Exception:
        return "upcoming"


@router.get("")
def list_catalysts(
    q: str = Query("", description="Search company/asset/event"),
    catalyst_type: str = Query("", description="Filter by catalyst type"),
    phase: str = Query("", description="Filter by clinical phase"),
    disease: str = Query("", description="Filter by disease area"),
    status_filter: str = Query("", description="overdue|imminent|upcoming|far"),
    year: int = Query(0, description="Filter by year"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
):
    today = date.today().isoformat()
    events: list[dict] = []

    # Source 1: 临床 table (richer data, 32k records with dates)
    clinical_rows = query("""
        SELECT "记录ID", "公司名称", "资产名称", "下一个催化剂", "催化剂类型",
               "催化剂预计时间", "催化剂确定性", "适应症", "临床期次",
               "数据状态", "结果判定", "试验ID"
        FROM "临床"
        WHERE "催化剂预计时间" IS NOT NULL AND "催化剂预计时间" != ''
    """)

    for r in clinical_rows:
        parsed = _parse_date(r.get("催化剂预计时间", ""))
        if not parsed:
            continue
        events.append(
            {
                "id": f"c-{r.get('记录ID', '')}",
                "source": "clinical",
                "company": r.get("公司名称", ""),
                "asset": r.get("资产名称", ""),
                "event": r.get("下一个催化剂", ""),
                "type": r.get("催化剂类型", "") or "Milestone",
                "raw_date": r.get("催化剂预计时间", ""),
                "date": parsed,
                "certainty": r.get("催化剂确定性", ""),
                "indication": r.get("适应症", ""),
                "phase": r.get("临床期次", ""),
                "data_status": r.get("数据状态", ""),
                "result": r.get("结果判定", ""),
                "trial_id": r.get("试验ID", ""),
                "status": _status(parsed, today),
            }
        )

    # Source 2: 资产 table (1k records — asset-level milestones)
    asset_rows = query("""
        SELECT "资产名称", "所属客户", "下一个临床节点", "节点预计时间",
               "催化剂日历", "临床阶段", "疾病领域", "适应症"
        FROM "资产"
        WHERE "节点预计时间" IS NOT NULL AND "节点预计时间" != ''
    """)

    for r in asset_rows:
        parsed = _parse_date(r.get("节点预计时间", ""))
        if not parsed:
            continue
        events.append(
            {
                "id": f"a-{r.get('所属客户', '')}-{r.get('资产名称', '')}",
                "source": "asset",
                "company": r.get("所属客户", ""),
                "asset": r.get("资产名称", ""),
                "event": r.get("下一个临床节点", ""),
                "type": "Milestone",
                "raw_date": r.get("节点预计时间", ""),
                "date": parsed,
                "certainty": "",
                "indication": r.get("适应症", "") or r.get("疾病领域", ""),
                "phase": r.get("临床阶段", ""),
                "data_status": "",
                "result": "",
                "trial_id": "",
                "status": _status(parsed, today),
                "calendar_detail": r.get("催化剂日历", ""),
            }
        )

    # Deduplicate: prefer clinical source over asset for same company+asset
    seen = set()
    deduped: list[dict] = []
    # Sort clinical first so they take priority
    events.sort(key=lambda e: (0 if e["source"] == "clinical" else 1, e["date"]))
    for e in events:
        key = (e["company"], e["asset"], e["date"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    # Apply filters
    filtered = deduped
    if q:
        ql = q.lower()
        filtered = [
            e
            for e in filtered
            if ql in (e["company"] or "").lower()
            or ql in (e["asset"] or "").lower()
            or ql in (e["event"] or "").lower()
        ]
    if catalyst_type:
        filtered = [e for e in filtered if catalyst_type.lower() in (e["type"] or "").lower()]
    if phase:
        filtered = [e for e in filtered if phase.lower() in (e["phase"] or "").lower()]
    if disease:
        dl = disease.lower()
        filtered = [e for e in filtered if dl in (e["indication"] or "").lower()]
    if year:
        filtered = [e for e in filtered if e["date"].startswith(str(year))]

    # Stats always reflect pre-status-filter totals so cards stay meaningful when filtering
    stats = {
        "total": len(filtered),
        "overdue": sum(1 for e in filtered if e["status"] == "overdue"),
        "imminent": sum(1 for e in filtered if e["status"] == "imminent"),
        "upcoming": sum(1 for e in filtered if e["status"] == "upcoming"),
        "far": sum(1 for e in filtered if e["status"] == "far"),
    }

    # Apply status_filter AFTER computing stats
    if status_filter:
        filtered = [e for e in filtered if e["status"] == status_filter]

    # Sort by date
    filtered.sort(key=lambda e: e["date"])

    # Paginate
    total = len(filtered)
    offset = (page - 1) * page_size
    page_data = filtered[offset : offset + page_size]

    # Catalyst types for filter dropdown
    all_types = sorted(set(e["type"] for e in deduped if e["type"]))

    return {
        "data": page_data,
        "stats": stats,
        "types": all_types,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
