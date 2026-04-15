"""Write endpoints for edit/delete operations — admin users only."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db import update_row, delete_row, distinct_values, rename_company, ALLOWED_TABLES
from auth import get_current_user
from field_policy import is_admin_user

router = APIRouter()


def _require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that enforces admin-only access."""
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="管理员权限不足")
    return user


class UpdateBody(BaseModel):
    fields: dict[str, str]
    pk2: str | None = None  # Second PK for composite keys (资产 table)


@router.put("/{table}/{pk_value}")
def update(table: str, pk_value: str, body: UpdateBody, _: dict = Depends(_require_admin)):
    if table not in ALLOWED_TABLES:
        raise HTTPException(400, f"Invalid table: {table}")
    if not body.fields:
        raise HTTPException(400, "No fields to update")

    pk = pk_value if body.pk2 is None else {"pk1": pk_value, "pk2": body.pk2}
    row = update_row(table, pk, body.fields)
    if not row:
        raise HTTPException(404, "Row not found")
    return row


class DeleteBody(BaseModel):
    pk2: str | None = None


@router.delete("/{table}/{pk_value}")
def delete(table: str, pk_value: str, body: DeleteBody | None = None, _: dict = Depends(_require_admin)):
    if table not in ALLOWED_TABLES:
        raise HTTPException(400, f"Invalid table: {table}")

    pk2 = body.pk2 if body else None
    pk = pk_value if pk2 is None else {"pk1": pk_value, "pk2": pk2}
    ok = delete_row(table, pk)
    if not ok:
        raise HTTPException(404, "Row not found")
    return {"deleted": True}


class RenameBody(BaseModel):
    new_name: str


@router.post("/rename-company/{old_name}")
def rename(old_name: str, body: RenameBody, _: dict = Depends(_require_admin)):
    """Rename a company, updating all cross-table references."""
    new_name = body.new_name.strip()
    if not new_name:
        raise HTTPException(400, "New name cannot be empty")
    try:
        ok = rename_company(old_name, new_name)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not ok:
        raise HTTPException(404, "Company not found")
    return {"renamed": True, "old_name": old_name, "new_name": new_name}


@router.get("/distinct/{table}/{column}")
def get_distinct(table: str, column: str, limit: int = 500):
    if table not in ALLOWED_TABLES:
        raise HTTPException(400, f"Invalid table: {table}")
    return distinct_values(table, column, limit)
