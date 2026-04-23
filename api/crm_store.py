"""
crm_store.py — CRM business data access layer.

Wraps the external ``crm_db`` workspace module to provide:
  - query / query_one / count helpers (SQLite ↔ PostgreSQL transparent)
  - paginate() for table-browsing endpoints
  - update_row / delete_row / rename_company for write operations
  - parse_numeric() for deal-value text fields

Manages the **CRM database** (公司 / 资产 / 交易 / 临床 / IP / MNC画像).
This is entirely separate from ``database.py``, which owns the **auth /
user Postgres pool** (users / sessions / credits / report_history).

Never import ``database.py`` from here, and never import ``crm_store``
from auth or session code — the two databases must stay independent.
"""

import math
import os
import re
import sys
import threading
from contextlib import contextmanager

from fastapi import HTTPException

# Import crm_db from the workspace scripts directory
_scripts_dir = os.path.expanduser("~/.openclaw/workspace/scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import config  # noqa: E402
import crm_db  # noqa: E402

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
    return "%s" if _is_pg() else "?"


# Match (in order): single-quoted string | double-quoted identifier | ?
# The first two alternatives swallow their contents so a literal '?' that
# happens to live inside a string like ``'what?'`` is preserved verbatim.
# Without this guard, the naive ``sql.replace('?', '%s')`` would also
# rewrite placeholder-lookalikes inside quoted sections and produce
# silently-broken SQL.
_QMARK_RE = re.compile(r"""'[^']*'|"[^"]*"|\?""")


def _qmark_to_percent(sql: str) -> str:
    """Rewrite ``?`` placeholders to psycopg2's ``%s`` form.

    Quoted strings and quoted identifiers pass through untouched.
    """
    return _QMARK_RE.sub(
        lambda m: "%s" if m.group() == "?" else m.group(),
        sql,
    )


# ── LIKE pattern escaping ────────────────────────────────────
#
# User-supplied strings (search boxes, LLM tool inputs, etc.) must not
# be dropped into LIKE patterns raw — a literal '%' or '_' from the
# user would be interpreted as a wildcard. That leaks weird matches
# ("A_B" matching "AxB") and lets a malicious/confused caller force a
# full table scan via "%%%%%%".
#
# Use ``like_contains(q)`` for the common ``%q%`` case, and pair it
# with :data:`LIKE_ESCAPE` in the SQL, e.g.:
#     WHERE col LIKE ? ESCAPE '\'
# ─────────────────────────────────────────────────────────────

LIKE_ESCAPE = "ESCAPE '\\'"
_LIKE_MAX = 100


def like_escape(q: str) -> str:
    """Escape %, _, and backslash so they match literally inside LIKE.

    Must be paired with the ``ESCAPE '\\'`` clause in the SQL.
    """
    if not q:
        return ""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def like_contains(q: str, max_len: int = _LIKE_MAX) -> str:
    """Build an escaped ``%q%`` substring pattern, clamped to ``max_len``.

    The clamp is a DoS guard — without it, a caller could pass a
    multi-kilobyte string and force expensive substring scans on
    every indexed column.
    """
    q = (q or "").strip()[:max_len]
    return f"%{like_escape(q)}%"


# ── Connection pool (read-only) ──────────────────────────────
#
# PostgreSQL: ThreadedConnectionPool avoids the 1-3 ms TCP handshake
# overhead of creating a new connection on every CRM query.  Since CRM
# queries run inside asyncio.to_thread() workers we need a thread-safe
# pool; psycopg2.ThreadedConnectionPool satisfies that requirement.
#
# SQLite: connections are in-process memory, so pooling adds complexity
# with negligible gain. We keep creating fresh read-only connections.
# ─────────────────────────────────────────────────────────────

_pg_read_pool = None  # psycopg2.pool.ThreadedConnectionPool | None
_pg_write_pool = None  # psycopg2.pool.ThreadedConnectionPool | None
_pg_pool_lock = threading.Lock()
_PG_POOL_MIN = 2
_PG_POOL_MAX = 10  # sized for asyncio.to_thread default pool (~8 workers)

# Writes are rare compared to reads (dashboard edits, company renames), so
# a small pool is plenty. Keeping them separate from the read pool prevents
# a burst of long-running edits from starving read-side latency.
_PG_WRITE_POOL_MIN = 1
_PG_WRITE_POOL_MAX = 4


def _get_pg_read_pool():
    """Lazy-init the PG read-connection pool (double-checked locking)."""
    global _pg_read_pool
    if _pg_read_pool is not None:
        return _pg_read_pool
    with _pg_pool_lock:
        if _pg_read_pool is not None:
            return _pg_read_pool
        import psycopg2.pool

        _pg_read_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=_PG_POOL_MIN,
            maxconn=_PG_POOL_MAX,
            dsn=crm_db.PG_DSN,
        )
        return _pg_read_pool


def _get_pg_write_pool():
    """Lazy-init the PG write-connection pool (double-checked locking)."""
    global _pg_write_pool
    if _pg_write_pool is not None:
        return _pg_write_pool
    with _pg_pool_lock:
        if _pg_write_pool is not None:
            return _pg_write_pool
        import psycopg2.pool

        _pg_write_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=_PG_WRITE_POOL_MIN,
            maxconn=_PG_WRITE_POOL_MAX,
            dsn=crm_db.PG_DSN,
        )
        return _pg_write_pool


def get_conn():
    """Borrow a read connection from the pool (PG) or create one (SQLite).

    Always pair with put_conn() — or use the _crm_conn() context manager.
    """
    if _is_pg():
        pool = _get_pg_read_pool()
        conn = pool.getconn()
        conn.autocommit = True  # read-only queries; no transaction needed
        return conn
    else:
        import sqlite3

        DB_PATH = config.CRM_DB_PATH
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn


def put_conn(conn) -> None:
    """Return a read connection to the pool (PG) or close it (SQLite)."""
    if _is_pg():
        _get_pg_read_pool().putconn(conn)
    else:
        conn.close()


@contextmanager
def _crm_conn():
    """Context manager for CRM read queries. Auto-returns to pool on exit."""
    conn = get_conn()
    try:
        yield conn
    finally:
        put_conn(conn)


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
    if _is_pg():
        sql = _qmark_to_percent(sql)
    with _crm_conn() as conn:
        return _fetchall(conn, sql, params)


def query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute SQL and return single dict or None."""
    if _is_pg():
        sql = _qmark_to_percent(sql)
    with _crm_conn() as conn:
        return _fetchone(conn, sql, params)


def count(sql: str, params: tuple = ()) -> int:
    """Execute a COUNT query and return the integer."""
    if _is_pg():
        sql = _qmark_to_percent(sql)
    with _crm_conn() as conn:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
        else:
            row = conn.execute(sql, params).fetchone()
        return row[0] if row else 0


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
    """Borrow a read-write connection for mutations.

    Callers MUST pair this with :func:`put_write_conn` (or use the
    :func:`_crm_write_conn` context manager which also handles commit /
    rollback). Plain ``conn.close()`` on a pooled psycopg2 connection
    shuts its socket down and leaks the pool slot.
    """
    if _is_pg():
        pool = _get_pg_write_pool()
        conn = pool.getconn()
        conn.autocommit = False
        return conn
    else:
        import sqlite3

        DB_PATH = config.CRM_DB_PATH
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn


def put_write_conn(conn) -> None:
    """Return a write connection to the pool (PG) or close it (SQLite).

    Rolls back any in-flight transaction before returning to the pool —
    psycopg2's pool will log a warning otherwise and the next borrower
    would inherit a dirty transaction state.
    """
    if _is_pg():
        try:
            conn.rollback()
        except Exception:
            pass
        _get_pg_write_pool().putconn(conn)
    else:
        conn.close()


@contextmanager
def _crm_write_conn():
    """Context manager for write connections. Rolls back + returns to pool
    on exception; caller is still responsible for ``conn.commit()`` on
    success. SQLite is closed outright.
    """
    conn = get_write_conn()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        put_write_conn(conn)


_backed_up_today = False
_backup_lock = threading.Lock()


def _ensure_backup():
    """Create a backup before the first write of the day (thread-safe).

    ``crm_db.backup()`` is idempotent per day, but two concurrent writes
    both seeing ``_backed_up_today=False`` would trigger redundant work.
    """
    global _backed_up_today
    if _backed_up_today:
        return
    with _backup_lock:
        if _backed_up_today:
            return
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

    with _crm_write_conn() as conn:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(
                f'UPDATE "{physical}" SET {", ".join(set_parts)} WHERE {where}',
                params,
            )
            conn.commit()
            import psycopg2.extras

            cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur2.execute(f'SELECT * FROM "{physical}" WHERE {where}', params[len(fields) :])
            row = cur2.fetchone()
            return dict(row) if row else None
        else:
            conn.execute(
                f'UPDATE "{physical}" SET {", ".join(set_parts)} WHERE {where}',
                params,
            )
            conn.commit()
            row = conn.execute(
                f'SELECT * FROM "{physical}" WHERE {where}', params[len(fields) :]
            ).fetchone()
            return dict(row) if row else None


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

    with _crm_write_conn() as conn:
        if _is_pg():
            cur = conn.cursor()
            cur.execute(f'DELETE FROM "{physical}" WHERE {where}', params)
            conn.commit()
            return cur.rowcount > 0
        else:
            cur = conn.execute(f'DELETE FROM "{physical}" WHERE {where}', params)
            conn.commit()
            return cur.rowcount > 0


def rename_company(old_name: str, new_name: str) -> bool:
    """Rename a company, updating all references across tables."""
    _ensure_backup()
    ph = _ph()
    with _crm_write_conn() as conn:
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
        stmts.append(
            (
                f'UPDATE "{physical_clinical}" SET "公司名称" = {ph} WHERE "公司名称" = {ph}',
                (new_name, old_name),
            )
        )
        stmts.append(
            (f'UPDATE "交易" SET "买方公司" = {ph} WHERE "买方公司" = {ph}', (new_name, old_name))
        )
        stmts.append(
            (
                f'UPDATE "交易" SET "卖方/合作方" = {ph} WHERE "卖方/合作方" = {ph}',
                (new_name, old_name),
            )
        )
        stmts.append(
            (f'UPDATE "IP" SET "关联公司" = {ph} WHERE "关联公司" = {ph}', (new_name, old_name))
        )

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


_SAFE_COLUMN_RE = re.compile(r"^[\w\u4e00-\u9fff()/\s·\-]+$")


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
    if _is_pg() and "?" in where_clause:
        where_clause = _qmark_to_percent(where_clause)

    with _crm_conn() as conn:
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
        limit_sql = f"LIMIT {ph} OFFSET {ph}"
        full_sql = f'SELECT {select} FROM "{physical}" {where_clause} {order_clause} {limit_sql}'
        rows = _fetchall(conn, full_sql, params + (page_size, offset))

    return {
        "data": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }
