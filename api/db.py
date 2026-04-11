"""
db.py — Thin wrapper around crm_db for the dashboard API.
Adds query helpers, pagination, and numeric parsing.
Supports both SQLite and PostgreSQL backends via crm_db.
"""

import os, sys, re, math
from fastapi import HTTPException

# Import crm_db from the workspace scripts directory
_scripts_dir = os.path.expanduser("~/.openclaw/workspace/scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import crm_db  # noqa: E402
import config  # noqa: E402

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

_is_pg = crm_db._is_pg


def _ph():
    """Placeholder: %s for PG, ? for SQLite."""
    return '%s' if _is_pg() else '?'


# ── helpers ──

def get_conn():
    """Create a new read connection (thread-safe for concurrent requests)."""
    if _is_pg():
        import psycopg2
        conn = psycopg2.connect(crm_db.PG_DSN)
        conn.autocommit = True  # read-only, no transaction needed
        return conn
    else:
        import sqlite3
        DB_PATH = config.CRM_DB_PATH
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn


def _fetchall(conn, sql, params=()):
    """Execute and return list[dict], backend-agnostic."""
    if _is_pg():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    else:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def _fetchone(conn, sql, params=()):
    """Execute and return single dict or None."""
    if _is_pg():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    else:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute SQL and return list of dicts."""
    # Convert ? to %s for PG
    if _is_pg():
        sql = sql.replace('?', '%s')
    conn = get_conn()
    try:
        return _fetchall(conn, sql, params)
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute SQL and return single dict or None."""
    if _is_pg():
        sql = sql.replace('?', '%s')
    conn = get_conn()
    try:
        return _fetchone(conn, sql, params)
    finally:
        conn.close()


def count(sql: str, params: tuple = ()) -> int:
    """Execute a COUNT query and return the integer."""
    if _is_pg():
        sql = sql.replace('?', '%s')
    conn = get_conn()
    try:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
        else:
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


def get_write_conn():
    """Create a read-write connection for mutations."""
    if _is_pg():
        import psycopg2
        conn = psycopg2.connect(crm_db.PG_DSN)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        DB_PATH = config.CRM_DB_PATH
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
    ph = _ph()

    set_parts = []
    params: list = []
    for col, val in fields.items():
        set_parts.append(f'"{col}" = {ph}')
        params.append(val)

    if isinstance(pk, tuple):
        where = f'"{pk[0]}" = {ph} AND "{pk[1]}" = {ph}'
        params.extend([pk_value["pk1"], pk_value["pk2"]])
    else:
        where = f'"{pk}" = {ph}'
        params.append(pk_value)

    conn = get_write_conn()
    try:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(
                f'UPDATE "{physical}" SET {", ".join(set_parts)} WHERE {where}',
                params,
            )
            conn.commit()
            import psycopg2.extras
            cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur2.execute(f'SELECT * FROM "{physical}" WHERE {where}', params[len(fields):])
            row = cur2.fetchone()
            return dict(row) if row else None
        else:
            conn.execute(
                f'UPDATE "{physical}" SET {", ".join(set_parts)} WHERE {where}',
                params,
            )
            conn.commit()
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
    ph = _ph()

    if isinstance(pk, tuple):
        where = f'"{pk[0]}" = {ph} AND "{pk[1]}" = {ph}'
        params = (pk_value["pk1"], pk_value["pk2"])
    else:
        where = f'"{pk}" = {ph}'
        params = (pk_value,)

    conn = get_write_conn()
    try:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(f'DELETE FROM "{physical}" WHERE {where}', params)
            conn.commit()
            return cur.rowcount > 0
        else:
            cur = conn.execute(f'DELETE FROM "{physical}" WHERE {where}', params)
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def rename_company(old_name: str, new_name: str) -> bool:
    """Rename a company, updating all references across tables."""
    _ensure_backup()
    ph = _ph()
    conn = get_write_conn()
    try:
        row = _fetchone(conn, f'SELECT 1 FROM "公司" WHERE "客户名称" = {ph}', (old_name,))
        if not row:
            return False
        dup = _fetchone(conn, f'SELECT 1 FROM "公司" WHERE "客户名称" = {ph}', (new_name,))
        if dup:
            raise ValueError(f"Company '{new_name}' already exists")

        stmts = [
            (f'UPDATE "公司" SET "客户名称" = {ph} WHERE "客户名称" = {ph}', (new_name, old_name)),
            (f'UPDATE "资产" SET "所属客户" = {ph} WHERE "所属客户" = {ph}', (new_name, old_name)),
        ]
        physical_clinical = crm_db._TABLE_ALIAS.get("临床", "临床")
        stmts.append((f'UPDATE "{physical_clinical}" SET "公司名称" = {ph} WHERE "公司名称" = {ph}', (new_name, old_name)))
        stmts.append((f'UPDATE "交易" SET "买方公司" = {ph} WHERE "买方公司" = {ph}', (new_name, old_name)))
        stmts.append((f'UPDATE "交易" SET "卖方/合作方" = {ph} WHERE "卖方/合作方" = {ph}', (new_name, old_name)))
        stmts.append((f'UPDATE "IP" SET "关联公司" = {ph} WHERE "关联公司" = {ph}', (new_name, old_name)))

        if _is_pg():
            cur = conn.cursor()
            for sql, p in stmts:
                cur.execute(sql, p)
            conn.commit()
        else:
            for sql, p in stmts:
                conn.execute(sql, p)
            conn.commit()
        return True
    finally:
        conn.close()


_SAFE_COLUMN_RE = re.compile(r'^[\w\u4e00-\u9fff()/\s·\-]+$')


def distinct_values(table: str, column: str, limit: int = 500) -> list[dict]:
    """Return distinct values + counts for a column."""
    if not _SAFE_COLUMN_RE.match(column):
        raise HTTPException(status_code=400, detail="Invalid column name")
    physical = crm_db._TABLE_ALIAS.get(table, table)
    ph = _ph()
    return query(
        f'''SELECT COALESCE(NULLIF("{column}", ''), 'Unknown') AS value,
                   COUNT(*) AS count
            FROM "{physical}"
            GROUP BY "{column}"
            ORDER BY count DESC
            LIMIT {ph}''',
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
    ph = _ph()

    # Convert any ? in caller's where clause to %s for PG
    if _is_pg() and '?' in where_clause:
        where_clause = where_clause.replace('?', '%s')

    conn = get_conn()
    try:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(f'SELECT COUNT(*) FROM "{physical}" {where_clause}', params)
            total = cur.fetchone()[0]
        else:
            row = conn.execute(
                f'SELECT COUNT(*) FROM "{physical}" {where_clause}', params
            ).fetchone()
            total = row[0] if row else 0

        offset = (page - 1) * page_size
        limit_sql = f'LIMIT {ph} OFFSET {ph}'
        full_sql = f'SELECT {select} FROM "{physical}" {where_clause} {order_clause} {limit_sql}'
        rows = _fetchall(conn, full_sql, params + (page_size, offset))
    finally:
        conn.close()

    return {
        "data": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }
