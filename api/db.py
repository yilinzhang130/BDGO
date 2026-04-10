"""
db.py — Thin wrapper around crm_db for the dashboard API.
Adds query helpers, pagination, and numeric parsing.
"""

import os, sys, sqlite3, re, math

# Import crm_db from the workspace scripts directory
_scripts_dir = os.path.expanduser("~/.openclaw/workspace/scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import crm_db  # noqa: E402
import config  # noqa: E402

DB_PATH = config.CRM_DB_PATH

# Table → primary key mapping
PK_MAP: dict[str, str | tuple[str, str]] = {
    "公司": "客户名称",
    "资产": ("资产名称", "所属客户"),
    "临床": "记录ID",
    "交易": "交易名称",
    "IP": "专利号",
    "MNC画像": "company_name",
    "LOE": "id",
}

ALLOWED_TABLES = set(PK_MAP.keys())

# ── helpers ──

def get_conn() -> sqlite3.Connection:
    """Create a new read-only connection (thread-safe for concurrent requests)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute SQL and return list of dicts."""
    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute SQL and return single dict or None."""
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count(sql: str, params: tuple = ()) -> int:
    """Execute a COUNT query and return the integer."""
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")

def parse_numeric(val) -> float | None:
    """Parse TEXT fields like '300.0', '$1.25B', '~6.8B' into float or None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    m = _NUM_RE.search(s)
    if m:
        num = float(m.group())
        upper = s.upper()
        if "B" in upper:
            num *= 1000  # convert to $M
        return num
    return None


def get_write_conn() -> sqlite3.Connection:
    """Create a read-write connection for mutations."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


_backed_up_today = False

def _ensure_backup():
    """Create a backup before the first write of the day."""
    global _backed_up_today
    if not _backed_up_today:
        crm_db.backup(tag="dashboard_edit")
        _backed_up_today = True


def update_row(table: str, pk_value: str | dict, fields: dict[str, str]) -> dict | None:
    """Update specific fields of a row. Returns the updated row."""
    if table not in ALLOWED_TABLES:
        return None
    _ensure_backup()

    physical = crm_db._TABLE_ALIAS.get(table, table)
    pk = PK_MAP[table]

    set_parts = []
    params: list = []
    for col, val in fields.items():
        set_parts.append(f'"{col}" = ?')
        params.append(val)

    if isinstance(pk, tuple):
        where = f'"{pk[0]}" = ? AND "{pk[1]}" = ?'
        params.extend([pk_value["pk1"], pk_value["pk2"]])
    else:
        where = f'"{pk}" = ?'
        params.append(pk_value)

    conn = get_write_conn()
    try:
        conn.execute(
            f'UPDATE "{physical}" SET {", ".join(set_parts)} WHERE {where}',
            params,
        )
        conn.commit()
        # Return updated row
        row = conn.execute(f'SELECT * FROM "{physical}" WHERE {where}', params[len(fields):]).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_row(table: str, pk_value: str | dict) -> bool:
    """Delete a row by primary key. Returns True if deleted."""
    if table not in ALLOWED_TABLES:
        return False
    _ensure_backup()

    physical = crm_db._TABLE_ALIAS.get(table, table)
    pk = PK_MAP[table]

    if isinstance(pk, tuple):
        where = f'"{pk[0]}" = ? AND "{pk[1]}" = ?'
        params = (pk_value["pk1"], pk_value["pk2"])
    else:
        where = f'"{pk}" = ?'
        params = (pk_value,)

    conn = get_write_conn()
    try:
        cur = conn.execute(f'DELETE FROM "{physical}" WHERE {where}', params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def rename_company(old_name: str, new_name: str) -> bool:
    """Rename a company, updating all references across tables."""
    _ensure_backup()
    conn = get_write_conn()
    try:
        # Check old exists
        row = conn.execute('SELECT 1 FROM "公司" WHERE "客户名称" = ?', (old_name,)).fetchone()
        if not row:
            return False
        # Check new doesn't already exist
        dup = conn.execute('SELECT 1 FROM "公司" WHERE "客户名称" = ?', (new_name,)).fetchone()
        if dup:
            raise ValueError(f"Company '{new_name}' already exists")
        # Update main table
        conn.execute('UPDATE "公司" SET "客户名称" = ? WHERE "客户名称" = ?', (new_name, old_name))
        # Update references in other tables
        conn.execute('UPDATE "资产" SET "所属客户" = ? WHERE "所属客户" = ?', (new_name, old_name))
        physical_clinical = crm_db._TABLE_ALIAS.get("临床", "临床")
        conn.execute(f'UPDATE "{physical_clinical}" SET "公司名称" = ? WHERE "公司名称" = ?', (new_name, old_name))
        conn.execute('UPDATE "交易" SET "买方公司" = ? WHERE "买方公司" = ?', (new_name, old_name))
        conn.execute('UPDATE "交易" SET "卖方/合作方" = ? WHERE "卖方/合作方" = ?', (new_name, old_name))
        conn.execute('UPDATE "IP" SET "关联公司" = ? WHERE "关联公司" = ?', (new_name, old_name))
        conn.commit()
        return True
    finally:
        conn.close()


def distinct_values(table: str, column: str, limit: int = 500) -> list[dict]:
    """Return distinct values + counts for a column."""
    physical = crm_db._TABLE_ALIAS.get(table, table)
    return query(
        f'''SELECT COALESCE(NULLIF("{column}", ''), 'Unknown') AS value,
                   COUNT(*) AS count
            FROM "{physical}"
            GROUP BY value
            ORDER BY count DESC
            LIMIT ?''',
        (limit,),
    )


def paginate(
    table: str,
    where: str = "",
    params: tuple = (),
    order_by: str = "",
    page: int = 1,
    page_size: int = 50,
    select: str = "*",
) -> dict:
    """Generic paginated query. Returns {data, total, page, page_size, total_pages}."""
    physical = crm_db._TABLE_ALIAS.get(table, table)
    where_clause = f"WHERE {where}" if where else ""
    order_clause = f"ORDER BY {order_by}" if order_by else ""

    # Single connection for both count + data query
    conn = get_conn()
    try:
        row = conn.execute(
            f'SELECT COUNT(*) FROM "{physical}" {where_clause}', params
        ).fetchone()
        total = row[0] if row else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            f'SELECT {select} FROM "{physical}" {where_clause} {order_clause} LIMIT ? OFFSET ?',
            params + (page_size, offset),
        ).fetchall()
    finally:
        conn.close()

    return {
        "data": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }
