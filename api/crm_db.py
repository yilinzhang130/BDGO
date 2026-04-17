#!/usr/bin/env python3
"""
crm_db.py — CRM 数据库抽象层 (SQLite / PostgreSQL 双后端)

替代原有的 CSV 读写，提供相同接口。
所有脚本只需 `from crm_db import load, save, backup` 即可切换。

后端切换：
    export CRM_BACKEND=postgresql    # 用 PostgreSQL（推荐，支持多writer）
    export CRM_BACKEND=sqlite        # 用 SQLite（默认，向后兼容）

PostgreSQL 连接串：
    export CRM_PG_DSN="dbname=bdgo"   # 默认值

Public API:
    load(table)          -> (list[dict], list[str])   与原 load_csv 完全兼容
    save(table, rows, cols)                            与原 write_csv 完全兼容
    backup(tag='')       创建备份
    export_csv(table, path=None)  导出 CSV（飞书 Bitable 用）
    export_all_csv(out_dir=None)  导出全部表
    get_conn()           获取数据库连接（高级用法）

作者: Claude (for Peter) | 2026-03-27 | PG迁移 2026-04-11

CHANGELOG (最新在上):
    2026-04-11  PG_DSN 默认值从 openclaw_crm 改为 bdgo（数据库统一）
    2026-04-11  PostgreSQL 后端升为推荐选项；SQLite 仅作只读备份
    2026-03-27  初始版本：SQLite 单后端，替代 CSV 读写
"""

import csv, json, os, sqlite3, shutil
from pathlib import Path
from datetime import datetime, timedelta

# ─── 自动加载 .env（如果环境变量未设置） ───
_env_file = Path.home() / '.openclaw' / '.env'
if _env_file.exists() and 'CRM_BACKEND' not in os.environ:
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v

# ─── 后端选择 ───
CRM_BACKEND = os.environ.get('CRM_BACKEND', 'sqlite').lower()
PG_DSN = os.environ.get('CRM_PG_DSN', 'dbname=bdgo')

# ─── 路径 ───
_default = os.path.expanduser('~/.openclaw/workspace')
BASE = Path(os.environ.get('OPENCLAW_WORKSPACE', _default))
CRM_DIR = BASE / 'crm-database'
DB_PATH = CRM_DIR / 'crm.db'
BACKUP_DIR = CRM_DIR / 'backups'

TABLES = ['公司', '资产', '临床', '交易', 'MNC画像', 'LOE', 'IP']

# Tracking status constants
STATUS_EXCLUDED = '排除'
STATUS_TRACKING = '追踪中'
STATUS_PENDING  = '待分类'

# 表名映射：逻辑名 → 物理表名（临床 v3 迁移）
_TABLE_ALIAS = {'临床': '临床'}

# 主键映射：逻辑表名 → 主键列名
_PK_MAP = {'公司': '客户名称', '资产': '资产名称', '临床': '记录ID', '交易': '交易名称', 'IP': '专利号'}

# 受保护列：upsert/save 时不会用空值覆盖已有非空值
PROTECTED_COLS = ['追踪状态', '英文名', '中文名', '曾用名', '母公司']

# ─── Schema (SQLite only, PG uses migrate_to_pg.py) ───
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS "公司" (
    "客户名称" TEXT NOT NULL PRIMARY KEY,
    "客户类型" TEXT,
    "主要核心pipeline的名字" TEXT,
    "主要资产或技术平台的类型" TEXT,
    "疾病领域" TEXT,
    "核心产品的阶段" TEXT,
    "核心资产主要适应症" TEXT,
    "跟进建议" TEXT,
    "市值/估值" TEXT,
    "年收入" TEXT,
    "Ticker" TEXT,
    "所处国家" TEXT,
    "网址" TEXT,
    "分析的日期" TEXT,
    "公司质量评分" TEXT,
    "下一个临床节点" TEXT,
    "节点预计时间" TEXT,
    "POS预测" TEXT,
    "催化剂日历" TEXT,
    "BD跟进优先级" TEXT,
    "推荐交易类型" TEXT,
    "潜在买方" TEXT,
    "现金" TEXT,
    "更改日期" TEXT,
    "联系人" TEXT,
    "BD来源" TEXT,
    "BD状态" TEXT,
    "BP来源" TEXT,
    "备注" TEXT
);

CREATE TABLE IF NOT EXISTS "资产" (
    "资产名称" TEXT NOT NULL,
    "所属客户" TEXT NOT NULL,
    "技术平台类别" TEXT,
    "疾病领域" TEXT,
    "适应症" TEXT,
    "临床阶段" TEXT,
    "POS预测" TEXT,
    "下一个临床节点" TEXT,
    "节点预计时间" TEXT,
    "催化剂日历" TEXT,
    "BD类别" TEXT,
    "是否核心资产" TEXT,
    "资产描述" TEXT,
    "创建时间" TEXT,
    "更新时间" TEXT,
    "资产代号" TEXT,
    "作用机制(MOA)" TEXT,
    "靶点" TEXT,
    "关键试验名称" TEXT,
    "竞品情况" TEXT,
    "差异化描述" TEXT,
    "峰值销售预测" TEXT,
    "合作方" TEXT,
    "风险因素" TEXT,
    "给药途径" TEXT,
    "BD优先级" TEXT,
    "监管状态" TEXT,
    "_enrich_confidence" TEXT,
    "_enrich_date" TEXT,
    "待查论文" TEXT,
    "BP来源" TEXT,
    "NCT_ID" TEXT,
    "入组人数" TEXT,
    "key" TEXT,
    "Q1_生物学" TEXT,
    "Q2_药物形式" TEXT,
    "Q3_临床监管" TEXT,
    "Q4_商业交易性" TEXT,
    "Q总分" TEXT,
    "差异化分级" TEXT,
    UNIQUE("资产名称", "所属客户")
);

CREATE TABLE IF NOT EXISTS "临床" (
    "记录ID" TEXT PRIMARY KEY,
    "试验ID" TEXT,
    "资产名称" TEXT,
    "公司名称" TEXT,
    "适应症" TEXT,
    "临床期次" TEXT,
    "试验设计类型" TEXT,
    "总入组人数" TEXT,
    "线数" TEXT,
    "入选人群" TEXT,
    "主要终点定义" TEXT,
    "臂名称" TEXT,
    "臂类型" TEXT,
    "臂入组人数" TEXT,
    "给药方案" TEXT,
    "主要终点名称" TEXT,
    "主要终点结果值" REAL,
    "主要终点单位" TEXT,
    "主要终点_HR" REAL,
    "主要终点_p值" TEXT,
    "主要终点_CI95" TEXT,
    "主要终点达成" TEXT,
    "次要终点1名称" TEXT,
    "次要终点1结果值" REAL,
    "次要终点1单位" TEXT,
    "次要终点2名称" TEXT,
    "次要终点2结果值" REAL,
    "次要终点2单位" TEXT,
    "次要终点3名称" TEXT,
    "次要终点3结果值" REAL,
    "次要终点3单位" TEXT,
    "Gr3plus_AE_pct" REAL,
    "AE_discontinue_pct" REAL,
    "关键AE描述" TEXT,
    "安全性标志" TEXT,
    "数据状态" TEXT,
    "数据截止日期" TEXT,
    "中位随访月数" REAL,
    "分析人群" TEXT,
    "临床综合评分" REAL,
    "结果判定" TEXT,
    "监管路径" TEXT,
    "白袍评估摘要" TEXT,
    "下一个催化剂" TEXT,
    "催化剂类型" TEXT,
    "催化剂预计时间" TEXT,
    "催化剂确定性" TEXT,
    "原始疗效文本" TEXT,
    "原始终点结果" TEXT,
    "原始试验设计" TEXT,
    "原始arms文本" TEXT,
    "评估日期" TEXT,
    "来源文件" TEXT,
    "来源链接" TEXT,
    "数据来源" TEXT,
    "备注" TEXT,
    "追踪状态" TEXT,
    "_schema_version" TEXT
);

CREATE TABLE IF NOT EXISTS "交易" (
    "交易名称" TEXT NOT NULL,
    "交易类型" TEXT,
    "买方公司" TEXT,
    "买方CRM状态" TEXT,
    "卖方/合作方" TEXT,
    "卖方CRM状态" TEXT,
    "资产名称" TEXT,
    "靶点" TEXT,
    "临床阶段" TEXT,
    "适应症" TEXT,
    "技术平台" TEXT,
    "首付款($M)" TEXT,
    "里程碑总额($M)" TEXT,
    "交易总额($M)" TEXT,
    "特许权结构" TEXT,
    "里程碑节点" TEXT,
    "宣布日期" TEXT,
    "新闻标题" TEXT,
    "来源链接" TEXT,
    "战略评分" TEXT,
    "战略解读" TEXT,
    "发现来源" TEXT,
    "发现时间" TEXT,
    "是否自动创建公司" TEXT,
    "备注" TEXT
);

-- 元数据表：记录每个表的列顺序
CREATE TABLE IF NOT EXISTS "_meta" (
    "table_name" TEXT PRIMARY KEY,
    "col_order" TEXT NOT NULL
);

-- ═══ MNC买方分析新表 (v2 DNA驱动) ═══

CREATE TABLE IF NOT EXISTS "MNC画像" (
    "company_name" TEXT NOT NULL PRIMARY KEY,
    "company_cn" TEXT DEFAULT '',
    "founded_year" TEXT DEFAULT '',
    "heritage_ta" TEXT DEFAULT '',
    "innovation_philosophy" TEXT DEFAULT '',
    "signature_deals" TEXT DEFAULT '[]',
    "risk_appetite" TEXT DEFAULT '',
    "deal_size_preference" TEXT DEFAULT '',
    "integration_success_rate" TEXT DEFAULT '',
    "annual_revenue" TEXT DEFAULT '',
    "annual_revenue_year" TEXT DEFAULT '',
    "ceo_name" TEXT DEFAULT '',
    "ceo_background" TEXT DEFAULT '',
    "cso_name" TEXT DEFAULT '',
    "cso_background" TEXT DEFAULT '',
    "head_bd_name" TEXT DEFAULT '',
    "head_bd_background" TEXT DEFAULT '',
    "commercial_capabilities" TEXT DEFAULT '{}',
    "regulatory_expertise" TEXT DEFAULT '{}',
    "dna_summary" TEXT DEFAULT '',
    "bd_pattern_theses" TEXT DEFAULT '[]',
    "sunk_cost_by_ta" TEXT DEFAULT '{}',
    "deal_type_preference" TEXT DEFAULT '{}',
    "last_updated" TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS "LOE" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "company" TEXT NOT NULL,
    "product_name" TEXT NOT NULL,
    "therapeutic_area" TEXT DEFAULT '',
    "annual_revenue" TEXT DEFAULT '',
    "revenue_year" TEXT DEFAULT '',
    "core_patent_expiry" TEXT DEFAULT '',
    "generic_biosimilar_status" TEXT DEFAULT '',
    "revenue_at_risk_3yr" TEXT DEFAULT '',
    "urgency_score" TEXT DEFAULT '',
    "bd_implication" TEXT DEFAULT '',
    "last_updated" TEXT DEFAULT '',
    UNIQUE("company", "product_name")
);

CREATE TABLE IF NOT EXISTS "IP" (
    "专利号" TEXT PRIMARY KEY,
    "专利持有人" TEXT DEFAULT '',
    "关联资产" TEXT DEFAULT '',
    "关联公司" TEXT DEFAULT '',
    "专利类型" TEXT DEFAULT '',
    "申请日" TEXT DEFAULT '',
    "授权日" TEXT DEFAULT '',
    "到期日" TEXT DEFAULT '',
    "PTE延期到期日" TEXT DEFAULT '',
    "权利要求摘要" TEXT DEFAULT '',
    "专利族" TEXT DEFAULT '',
    "状态" TEXT DEFAULT '',
    "管辖区" TEXT DEFAULT '',
    "Orange_Book" TEXT DEFAULT '',
    "来源" TEXT DEFAULT '',
    "备注" TEXT DEFAULT '',
    "追踪状态" TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_IP_公司 ON "IP"("关联公司");
CREATE INDEX IF NOT EXISTS idx_IP_资产 ON "IP"("关联资产");
CREATE INDEX IF NOT EXISTS idx_IP_到期日 ON "IP"("到期日");
CREATE INDEX IF NOT EXISTS idx_LOE_company ON "LOE"("company");

-- 索引
CREATE INDEX IF NOT EXISTS idx_公司_ticker ON "公司"("Ticker");
CREATE INDEX IF NOT EXISTS idx_资产_客户 ON "资产"("所属客户");
CREATE INDEX IF NOT EXISTS idx_资产_阶段 ON "资产"("临床阶段");
CREATE INDEX IF NOT EXISTS idx_临床_试验ID ON "临床"("试验ID");
CREATE INDEX IF NOT EXISTS idx_临床_公司 ON "临床"("公司名称");
CREATE INDEX IF NOT EXISTS idx_临床_资产 ON "临床"("资产名称");
CREATE INDEX IF NOT EXISTS idx_临床_数据状态 ON "临床"("数据状态");
CREATE INDEX IF NOT EXISTS idx_临床_臂类型 ON "临床"("臂类型");
CREATE INDEX IF NOT EXISTS idx_交易_买方 ON "交易"("买方公司");
CREATE INDEX IF NOT EXISTS idx_交易_卖方 ON "交易"("卖方/合作方");

-- 查重防线：公司英文名/中文名部分唯一索引（空值和"无"不参与约束）
CREATE UNIQUE INDEX IF NOT EXISTS idx_公司_英文名_unique
    ON "公司"("英文名") WHERE "英文名" != '' AND "英文名" != '无';
CREATE UNIQUE INDEX IF NOT EXISTS idx_公司_中文名_unique
    ON "公司"("中文名") WHERE "中文名" != '' AND "中文名" != '无';
"""

# ─── 连接管理 ───
_conn = None

def _is_pg():
    return CRM_BACKEND == 'postgresql'


def get_conn():
    """获取数据库连接（模块级单例）
    SQLite: sqlite3.Connection
    PostgreSQL: psycopg2.connection
    """
    global _conn
    if _conn is None:
        if _is_pg():
            import psycopg2
            import psycopg2.extras
            _conn = psycopg2.connect(PG_DSN)
            _conn.autocommit = False
        else:
            CRM_DIR.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(DB_PATH), timeout=30)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA_SQL)
    return _conn


def get_raw_conn():
    """获取原始数据库连接，供需要直接SQL的脚本使用。
    返回 (conn, backend) 其中 backend ∈ {'postgresql', 'sqlite'}
    调用方可据此调整SQL语法。

    用法:
        from crm_db import get_raw_conn
        conn, backend = get_raw_conn()
        ph = '%s' if backend == 'postgresql' else '?'
    """
    return get_conn(), CRM_BACKEND


def connect():
    """sqlite3.connect() 的直接替代品。

    返回一个兼容连接对象：
    - PG后端: 自动把 SQL 中的 ? 转为 %s，返回 dict-like rows
    - SQLite后端: 行为和 sqlite3.connect() 完全一致

    用法（脚本只需改一行）:
        # 旧: conn = sqlite3.connect('/path/to/crm.db')
        # 新: conn = crm_db.connect()
        conn = crm_db.connect()
        rows = conn.execute('SELECT * FROM "公司" WHERE "客户名称" = ?', ('xxx',)).fetchall()
    """
    if _is_pg():
        return _PgCompatConnection()
    else:
        CRM_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn


class _PgCompatCursor:
    """PG cursor包装器，兼容 sqlite3.Cursor 接口。
    自动把 ? 转为 %s，返回 dict-like rows。
    """
    def __init__(self, pg_conn):
        import psycopg2.extras
        self._conn = pg_conn
        self._cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self.lastrowid = None
        self.rowcount = 0
        self.description = None

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        self._cur.execute(sql, params or ())
        self.description = self._cur.description
        self.rowcount = self._cur.rowcount
        return self

    def executemany(self, sql, params_list):
        sql = sql.replace('?', '%s')
        self._cur.executemany(sql, params_list)
        self.rowcount = self._cur.rowcount
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in self._cur.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        return [dict(r) for r in rows]

    def close(self):
        self._cur.close()


class _PgCompatConnection:
    """PG连接包装器，兼容 sqlite3.Connection 接口。
    支持 execute/executemany/commit/close/with 语法。
    """
    def __init__(self):
        import psycopg2
        self._conn = psycopg2.connect(PG_DSN)
        self._conn.autocommit = False

    def execute(self, sql, params=None):
        cur = _PgCompatCursor(self._conn)
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = _PgCompatCursor(self._conn)
        cur.executemany(sql, params_list)
        return cur

    def executescript(self, sql):
        """执行多条SQL（PG不支持executescript，用execute代替）"""
        cur = self._conn.cursor()
        cur.execute(sql)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return _PgCompatCursor(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        return False


def _placeholder():
    """返回参数占位符: SQLite用?, PG用%s"""
    return '%s' if _is_pg() else '?'


def _execute(conn, sql, params=None):
    """统一执行SQL，处理PG/SQLite差异"""
    if _is_pg():
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur
    else:
        return conn.execute(sql, params or ())


def _fetchall_dicts(conn, sql, params=None):
    """执行查询并返回 list[dict]"""
    if _is_pg():
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]
    else:
        cursor = conn.execute(sql, params or ())
        cols = [d[0] for d in cursor.description] if cursor.description else []
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _get_table_cols(conn, table):
    """获取表的列名列表"""
    if _is_pg():
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
            (table,)
        )
        return [r[0] for r in cur.fetchall()]
    else:
        return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _col_order(table: str) -> list[str]:
    """从 _meta 表读取列顺序"""
    return _col_order_phys(table, table)

def _col_order_phys(phys_table: str, meta_key: str) -> list[str]:
    """从 _meta 表读取列顺序，支持物理表名与逻辑表名不同"""
    conn = get_conn()
    ph = _placeholder()
    for key in (meta_key, phys_table):
        rows = _fetchall_dicts(conn, f'SELECT col_order FROM _meta WHERE table_name = {ph}', (key,))
        if rows:
            return json.loads(rows[0]['col_order'])
    return _get_table_cols(conn, phys_table)


# ─── Public API ───

def _physical_table(table: str) -> str:
    """逻辑表名 → 物理表名"""
    return _TABLE_ALIAS.get(table, table)

def load(table: str) -> tuple[list[dict], list[str]]:
    """加载整张表，返回 (rows, cols)，与原 load_csv 完全兼容"""
    if table not in TABLES:
        raise ValueError(f"未知表名: {table}，可选: {TABLES}")
    conn = get_conn()
    phys = _physical_table(table)
    cols = _col_order_phys(phys, table)
    quoted = ', '.join(f'"{c}"' for c in cols)
    rows = _fetchall_dicts(conn, f'SELECT {quoted} FROM "{phys}"')
    # Ensure consistent col ordering in dicts
    result = []
    for row in rows:
        result.append({c: row.get(c, '') for c in cols})
    return result, cols


def is_excluded(row: dict) -> bool:
    """Check if a row has 排除 tracking status (with strip)."""
    return (row.get('追踪状态') or '').strip() == STATUS_EXCLUDED


def load_enum(table: str = None, field: str = None) -> dict[tuple[str,str], set[str]]:
    """从 _enum 表加载合法值。返回 {(表名, 字段名): {合法值, ...}}。"""
    conn = get_conn()
    ph = _placeholder()
    sql = 'SELECT "表名", "字段名", "合法值" FROM _enum WHERE 1=1'
    params = []
    if table:
        sql += f' AND "表名"={ph}'; params.append(table)
    if field:
        sql += f' AND "字段名"={ph}'; params.append(field)
    rows = _fetchall_dicts(conn, sql, params)
    result: dict[tuple[str,str], set[str]] = {}
    for r in rows:
        key = (r['表名'], r['字段名'])
        result.setdefault(key, set()).add(r['合法值'])
    return result


def validate_enum(table: str, rows: list[dict]) -> list[dict]:
    """校验 rows 中的枚举字段，返回违规列表。"""
    enums = load_enum(table)
    violations = []
    pk_map = {'公司': '客户名称', '资产': '资产名称', '临床': '记录ID', '交易': '交易名称'}
    pk = pk_map.get(table, '')
    for row in rows:
        for (t, f), valid in enums.items():
            val = (row.get(f) or '').strip()
            if not val:
                continue
            if f == '交易类型':
                parts = [p.strip() for p in val.split(';') if p.strip()]
                bad = [p for p in parts if p not in valid]
                if bad:
                    violations.append({'row_key': row.get(pk, ''), 'field': f,
                                       'value': val, 'invalid_parts': bad,
                                       'valid_values': sorted(valid)})
            elif val not in valid:
                violations.append({'row_key': row.get(pk, ''), 'field': f,
                                   'value': val, 'valid_values': sorted(valid)})
    return violations


def save(table: str, rows: list[dict], cols: list[str]):
    """替换整张表的数据（原子事务），与原 write_csv 完全兼容。

    ⚠️  PostgreSQL 模式下此函数会 DELETE 整表再重建 — 仅适合小表或单 agent。
    多 agent 并发写入时，请用 crm_db.connect() + 直接 UPDATE/INSERT SQL。
    临床表(24k+行)等大表慎用此函数，建议直接用 SQL UPDATE。
    """
    if table not in TABLES:
        raise ValueError(f"未知表名: {table}，可选: {TABLES}")
    if _is_pg() and len(rows) > 5000:
        import warnings
        warnings.warn(
            f"[crm_db.save] PostgreSQL模式下 save('{table}') 将 DELETE+INSERT {len(rows)} 行。"
            "大表操作建议改用直接 SQL UPDATE。", stacklevel=2
        )

    conn = get_conn()
    phys = _physical_table(table)
    cols = list(cols)
    ph = _placeholder()

    # ── 保护系统管理列 ──
    existing_db_cols = set(_get_table_cols(conn, phys))
    active_protected = [pc for pc in PROTECTED_COLS if pc in existing_db_cols]

    if active_protected:
        pk = _PK_MAP.get(table, 'rowid')
        prot_cols_sql = ', '.join(f'"{c}"' for c in active_protected)

        if pk == 'rowid' and not _is_pg():
            old_rows_raw = _fetchall_dicts(conn, f'SELECT rowid, {prot_cols_sql} FROM "{phys}"')
            old_map = {}
            for r in old_rows_raw:
                old_map[r.get('rowid')] = {c: r.get(c) for c in active_protected}
        else:
            old_rows_raw = _fetchall_dicts(conn, f'SELECT "{pk}", {prot_cols_sql} FROM "{phys}"')
            old_map = {}
            for r in old_rows_raw:
                key = (r.get(pk) or '').strip()
                if key:
                    old_map[key] = {c: r.get(c) for c in active_protected}

        for pcol in active_protected:
            if pcol not in cols:
                cols.append(pcol)

        for row in rows:
            row_key = (row.get(pk, '') or '').strip() if pk != 'rowid' else None
            old_vals = old_map.get(row_key, {}) if row_key else {}
            for pcol in active_protected:
                cur_val = (row.get(pcol) or '').strip()
                if not cur_val and old_vals.get(pcol):
                    row[pcol] = old_vals[pcol]
                elif pcol not in row:
                    row[pcol] = old_vals.get(pcol, '')

    # ── 资产表: Q总分 自动计算 ──
    if table == '资产':
        if 'Q总分' not in cols:
            cols.append('Q总分')
        for row in rows:
            q_vals = []
            for qf in ('Q1_生物学', 'Q2_药物形式', 'Q3_临床监管', 'Q4_商业交易性'):
                v = str(row.get(qf) or '').strip()
                if v and v.isdigit():
                    q_vals.append(int(v))
            if len(q_vals) == 4:
                row['Q总分'] = str(sum(q_vals))

    quoted_cols = ', '.join(f'"{c}"' for c in cols)
    placeholders = ', '.join([ph] * len(cols))

    if _is_pg():
        cur = conn.cursor()
        try:
            cur.execute(f'DELETE FROM "{phys}"')
            for row in rows:
                vals = [row.get(c, '') for c in cols]
                cur.execute(
                    f'INSERT INTO "{phys}" ({quoted_cols}) VALUES ({placeholders})',
                    vals
                )
            cur.execute(
                f'INSERT INTO _meta (table_name, col_order) VALUES (%s, %s) '
                f'ON CONFLICT (table_name) DO UPDATE SET col_order = EXCLUDED.col_order',
                (table, json.dumps(cols, ensure_ascii=False))
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    else:
        with conn:
            conn.execute(f'DELETE FROM "{phys}"')
            conn.executemany(
                f'INSERT OR REPLACE INTO "{phys}" ({quoted_cols}) VALUES ({placeholders})',
                [[row.get(c, '') for c in cols] for row in rows]
            )
            conn.execute(
                'INSERT OR REPLACE INTO _meta (table_name, col_order) VALUES (?, ?)',
                (table, json.dumps(cols, ensure_ascii=False))
            )


def upsert_row(table: str, data: dict) -> tuple[str, str]:
    """单条记录智能写入：查重 → INSERT / UPDATE / SKIP

    对公司表：调用 crm_ingest.py 的 find_existing_company() 做6轮模糊匹配
    对资产表：调用 find_existing_asset() 做2轮匹配
    对交易表：调用 find_existing_deal() 做3路匹配
    对临床表：调用 find_existing_clinical() 做2层匹配
    其他表：仅用PK约束

    Returns: (action, key)
        action ∈ {'INSERT', 'UPDATE', 'SKIP'}
        key = 匹配/新建的主键值
    """
    if table not in TABLES:
        raise ValueError(f"未知表名: {table}，可选: {TABLES}")

    conn = get_conn()
    phys = _physical_table(table)
    pk = _PK_MAP.get(table, '')
    ph = _placeholder()

    # ── Step 1: 加载现有数据用于查重 ──
    rows, cols = load(table)

    # ── Step 2: 查重 ──
    matched = None
    if table == '公司':
        from crm_ingest import find_existing_company
        company_name = (data.get('客户名称') or '').strip()
        if company_name:
            matched = find_existing_company(company_name, rows)
    elif table == '资产':
        from crm_ingest import find_existing_asset
        asset_name = (data.get('资产名称') or '').strip()
        company_name = (data.get('所属客户') or '').strip()
        if asset_name:
            matched = find_existing_asset(asset_name, company_name, rows)
    elif table == '交易':
        from crm_ingest import find_existing_deal
        matched = find_existing_deal(
            (data.get('交易名称') or '').strip(),
            (data.get('买方公司') or '').strip(),
            (data.get('卖方/合作方') or '').strip(),
            (data.get('资产名称') or '').strip(),
            rows
        )
    elif table == '临床':
        from crm_ingest import find_existing_clinical
        matched = find_existing_clinical(
            (data.get('试验ID') or '').strip(),
            (data.get('资产名称') or '').strip(),
            (data.get('公司名称') or '').strip(),
            (data.get('临床期次') or '').strip(),
            (data.get('适应症') or '').strip(),
            rows
        )
    else:
        if pk:
            pk_val = (data.get(pk) or '').strip()
            if pk_val:
                for r in rows:
                    if (r.get(pk) or '').strip() == pk_val:
                        matched = r
                        break

    # ── Step 3: 执行写入 ──
    if matched:
        matched_key = (matched.get(pk) or '').strip() if pk else ''

        set_clauses, values = [], []
        for col, val in data.items():
            if col == pk:
                continue
            new_val = (str(val) if val is not None else '').strip()
            if not new_val:
                continue
            existing_val = (str(matched.get(col, '')) if matched.get(col) is not None else '').strip()
            if col in PROTECTED_COLS and existing_val:
                continue
            if new_val != existing_val:
                set_clauses.append(f'"{col}"={ph}')
                values.append(new_val)

        if not set_clauses:
            return ('SKIP', matched_key)

        if table == '交易' and not pk:
            if _is_pg():
                # PG: use ctid
                cur = conn.cursor()
                cur.execute(
                    f'SELECT ctid FROM "交易" WHERE "交易名称"={ph} LIMIT 1',
                    ((matched.get('交易名称') or ''),)
                )
                row = cur.fetchone()
                if row:
                    values.append(row[0])
                    cur.execute(f'UPDATE "{phys}" SET {", ".join(set_clauses)} WHERE ctid={ph}', values)
                    conn.commit()
                    return ('UPDATE', matched.get('交易名称', ''))
                return ('SKIP', matched.get('交易名称', ''))
            else:
                cursor = conn.execute(
                    f'SELECT rowid FROM "交易" WHERE "交易名称"={ph} LIMIT 1',
                    ((matched.get('交易名称') or ''),)
                )
                row = cursor.fetchone()
                if row:
                    values.append(row[0])
                    conn.execute(f'UPDATE "{phys}" SET {", ".join(set_clauses)} WHERE rowid={ph}', values)
                    conn.commit()
                    return ('UPDATE', matched.get('交易名称', ''))
                return ('SKIP', matched.get('交易名称', ''))
        else:
            values.append(matched_key)
            _execute(conn, f'UPDATE "{phys}" SET {", ".join(set_clauses)} WHERE "{pk}"={ph}', values)
            conn.commit()
            return ('UPDATE', matched_key)

    # ── Step 4: INSERT新行 ──
    data_cols = list(data.keys())
    quoted = ', '.join(f'"{c}"' for c in data_cols)
    placeholders = ', '.join([ph] * len(data_cols))
    data_values = [data.get(c, '') for c in data_cols]

    _execute(conn, f'INSERT INTO "{phys}" ({quoted}) VALUES ({placeholders})', data_values)
    conn.commit()
    new_key = (data.get(pk) or '').strip() if pk else ''
    return ('INSERT', new_key)


def backup(tag: str = '', force: bool = False):
    """创建数据库备份
    SQLite: 文件级备份
    PostgreSQL: pg_dump到备份目录
    """
    if _is_pg():
        return _backup_pg(tag, force)
    else:
        return _backup_sqlite(tag, force)


def _backup_sqlite(tag: str = '', force: bool = False):
    if not DB_PATH.exists():
        return
    today = datetime.now().strftime('%Y%m%d')
    if not force:
        BACKUP_DIR.mkdir(exist_ok=True)
        if any(BACKUP_DIR.glob(f'crm_{today}_*.db')):
            return
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = f'_{tag}' if tag else ''
    dst = BACKUP_DIR / f'crm_{ts}{suffix}.db'
    conn = get_conn()
    bak = sqlite3.connect(str(dst))
    conn.backup(bak)
    bak.close()
    _cleanup_old_backups(keep_days=7)
    return dst


def _backup_pg(tag: str = '', force: bool = False):
    """PostgreSQL备份：pg_dump到SQL文件"""
    import subprocess
    today = datetime.now().strftime('%Y%m%d')
    BACKUP_DIR.mkdir(exist_ok=True)
    if not force:
        if any(BACKUP_DIR.glob(f'crm_{today}_*.sql')):
            return
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = f'_{tag}' if tag else ''
    dst = BACKUP_DIR / f'crm_{ts}{suffix}.sql'
    # Use pg_dump
    pg_dump = shutil.which('pg_dump') or '/opt/homebrew/opt/postgresql@17/bin/pg_dump'
    result = subprocess.run(
        [pg_dump, PG_DSN.replace('dbname=', ''), '-f', str(dst)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [backup] pg_dump error: {result.stderr}")
        return None
    _cleanup_old_backups(keep_days=7)
    return dst


def _cleanup_old_backups(keep_days: int = 7):
    if not BACKUP_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for pattern in ('crm_*.db', 'crm_*.sql'):
        for f in BACKUP_DIR.glob(pattern):
            try:
                date_str = f.name.split('_')[1]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                if file_date < cutoff:
                    f.unlink()
                    removed += 1
            except (IndexError, ValueError):
                continue
    if removed:
        print(f"  [backup] 清理了 {removed} 个过期备份")


def export_csv(table: str, path: Path = None):
    """导出表为 CSV"""
    rows, cols = load(table)
    if path is None:
        path = CRM_DIR / f'{table}.csv'
    path = Path(path)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return path


def export_all_csv(out_dir: Path = None):
    """导出全部表为 CSV"""
    if out_dir is None:
        out_dir = CRM_DIR
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for t in TABLES:
        paths[t] = export_csv(t, out_dir / f'{t}.csv')
    return paths


# ─── CLI ───
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='CRM 数据库工具')
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('info', help='显示数据库统计')
    p_export = sub.add_parser('export', help='导出全部表为 CSV')
    p_export.add_argument('--dir', type=Path, default=None, help='输出目录')
    sub.add_parser('backup', help='创建数据库备份')

    args = parser.parse_args()

    if args.cmd == 'info':
        conn = get_conn()
        backend = "PostgreSQL" if _is_pg() else f"SQLite ({DB_PATH})"
        print(f"后端: {backend}")
        if not _is_pg():
            print(f"大小: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
        for t in TABLES:
            phys = _physical_table(t)
            rows = _fetchall_dicts(conn, f'SELECT COUNT(*) as cnt FROM "{phys}"')
            count = rows[0]['cnt'] if rows else 0
            print(f"  {t}: {count:,} rows")
        if not _is_pg():
            rows = _fetchall_dicts(conn, 'PRAGMA integrity_check')
            print(f"\n完整性检查: {rows[0].get('integrity_check', 'unknown') if rows else 'N/A'}")

    elif args.cmd == 'export':
        paths = export_all_csv(args.dir)
        for t, p in paths.items():
            print(f"  {t} → {p}")

    elif args.cmd == 'backup':
        dst = backup()
        print(f"备份: {dst}")

    else:
        parser.print_help()
