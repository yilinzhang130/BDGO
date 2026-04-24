"""MNC Buyer Profile endpoints — HTTP contract only; SQL in services/crm/buyers."""

from urllib.parse import unquote

from auth import public_api
from crm_store import LIKE_ESCAPE, like_contains
from fastapi import APIRouter, HTTPException, Query
from services.crm import buyers as buyers_service
from services.crm.list_view import PaginatedResponse, list_table_view

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
@public_api
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
        conditions.append(
            f'("company_name" LIKE ? {LIKE_ESCAPE} OR "company_cn" LIKE ? {LIKE_ESCAPE} OR "heritage_ta" LIKE ? {LIKE_ESCAPE})'
        )
        params.extend([like_contains(q)] * 3)

    where = " AND ".join(conditions) if conditions else ""
    return list_table_view(
        "MNC画像",
        where=where,
        params=tuple(params),
        sort=sort,
        order=order,
        sort_allowlist={
            "company_name",
            "heritage_ta",
            "annual_revenue",
            "last_updated",
            "risk_appetite",
            "deal_size_preference",
        },
        default_sort="company_name",
        page=page,
        page_size=page_size,
    )


@router.get("/{name}")
@public_api
def get_buyer(name: str):
    row = buyers_service.fetch_buyer(unquote(name))
    if row is None:
        raise HTTPException(status_code=404, detail="Buyer profile not found")
    return row
