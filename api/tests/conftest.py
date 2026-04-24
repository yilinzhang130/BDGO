"""
conftest.py — 全局 pytest fixtures（测试积木块）

概念解释：
    fixture = 测试运行前自动准备好的东西（比如"已登录用户"、"测试数据库"）
    @pytest.fixture 装饰器把一个函数变成可被任何测试函数直接注入的积木
    yield 之前是"准备"，yield 之后是"清理"（类似 try/finally）

fixture 的 scope：
    "function"（默认）— 每个测试函数单独执行一次
    "session"          — 整个测试运行期间只执行一次（适合昂贵的准备工作）
"""

from __future__ import annotations

import os
import sys
import types

import pytest

# ── 把 api/ 目录加到 Python path，让 import 能找到模块 ──────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── 在 import 任何 app 代码之前，先设好环境变量 ──────────────────────
# 这样 config.py 不会因为缺 JWT_SECRET 而 hard fail
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-long-enough!")
os.environ.setdefault("DATABASE_URL", "")  # 空 = 测试不连真实 DB
# ADMIN_SECRET 设成一个非空常量；如果不设，auth.require_admin_header
# 会 raise 503（"Admin not configured"）而不是我们想测的 403。
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-unknown-to-fake-users")

# ── 注入外部依赖的 stub ──────────────────────────────────────────────
# crm_match 和 crm_db 都住在 ~/.openclaw/workspace/scripts/ —— 本地可能
# 有、CI runner 上肯定没有。测试不应该依赖外部文件系统，所以注入最小
# stub 模块让 api 代码能 import。
# 真正查 CRM 数据的测试（若将来出现）应该 mock crm_store 层，不是
# 依赖这个 stub 的行为。
if "crm_match" not in sys.modules:
    _stub = types.ModuleType("crm_match")

    def _find_existing_company(name: str, threshold: float = 0.85):
        """Stub: 测试环境里总是返回 None（找不到模糊匹配）"""
        return None, None

    def _normalize_name(name: str) -> str:
        """Stub: 直接返回原名"""
        return (name or "").strip().lower()

    _stub.find_existing_company = _find_existing_company
    _stub.normalize_name = _normalize_name
    sys.modules["crm_match"] = _stub

if "crm_db" not in sys.modules:
    _stub = types.ModuleType("crm_db")

    # crm_store.py reads ``crm_db._is_pg`` at import time (module-level
    # constant). Everything else it uses (PG_DSN, _TABLE_ALIAS,
    # _col_order_phys, backup, etc.) is inside functions — only tests
    # that actually exercise CRM queries will need those stubbed.
    _stub._is_pg = lambda: False
    _stub.PG_DSN = ""
    _stub._TABLE_ALIAS = {}
    sys.modules["crm_db"] = _stub


# ════════════════════���══════════════════════════════════════��════
# 用户 fixtures — 各种权限的模拟用户 dict
# ═════════════════════��══════════════════════════════════════════


# 全部用户都需要携带 UserResponse schema 里的必填字段
# （avatar_url / provider / created_at / last_login）—— 否则
# /api/auth/me 的 response_model 校验会抛 ValidationError → 500。


def _base_user() -> dict:
    """公共字段，子类加角色位。"""
    return {
        "avatar_url": None,
        "provider": "email",
        "created_at": "2026-04-01T00:00:00",
        "last_login": None,
        "company": None,
        "title": None,
        "phone": None,
        "bio": None,
        "preferences_json": None,
    }


@pytest.fixture
def external_user():
    """模拟一个普通外部用户（合作伙伴）"""
    return {
        **_base_user(),
        "id": "user-ext-001",
        "email": "partner@example.com",
        "name": "外部用户",
        "is_admin": False,
        "is_internal": False,
        "is_active": True,
    }


@pytest.fixture
def internal_user():
    """模拟一个内部员工（可以看隐藏字段）"""
    return {
        **_base_user(),
        "id": "user-int-001",
        "email": "analyst@yafocapital.com",
        "name": "内部分析师",
        "is_admin": False,
        "is_internal": True,
        "is_active": True,
    }


@pytest.fixture
def admin_user():
    """模拟一个管理员"""
    return {
        **_base_user(),
        "id": "user-adm-001",
        "email": "admin@yafocapital.com",
        "name": "管理员",
        "is_admin": True,
        "is_internal": True,
        "is_active": True,
    }


# ════════════════════════════════════════════════════════════════
# JWT token fixtures — 生成真实可用的 token
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def external_token(external_user):
    """为外部用户生成 JWT token"""
    from auth import create_token

    return create_token(external_user["id"], external_user["email"])


@pytest.fixture
def internal_token(internal_user):
    """为内部用户生成 JWT token"""
    from auth import create_token

    return create_token(internal_user["id"], internal_user["email"])


@pytest.fixture
def admin_token(admin_user):
    """为管理员生成 JWT token"""
    from auth import create_token

    return create_token(admin_user["id"], admin_user["email"])


# ═══════════════════════��════════════════════════════════════════
# HTTP headers fixtures — 直接传给 TestClient
# ═════════════════════════════════════════════════════���══════════


@pytest.fixture
def ext_headers(external_token):
    return {"Authorization": f"Bearer {external_token}"}


@pytest.fixture
def int_headers(internal_token):
    return {"Authorization": f"Bearer {internal_token}"}


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ════════════════════════════════════════════════════════════════
# FastAPI TestClient fixture
# ══════════════════════════════════════════════════��═════════════


@pytest.fixture(scope="session")
def app():
    """
    创建 FastAPI app 实例（整个测试 session 只创建一次）

    注意：我们把 get_current_user 的 DB 查询 mock 掉，
    这样测试不需要连接真实 Postgres。
    """
    from main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app, external_user, internal_user, admin_user, monkeypatch):
    """
    返回一个 TestClient，并把数据库依赖 mock 掉。

    monkeypatch 是 pytest 内置的：能临时替换任意函数/属性，
    测试结束后自动还原，不影响其他测试。
    """
    from auth import get_current_user, get_optional_user
    from fastapi import Header
    from fastapi.testclient import TestClient

    # 用一个查表函数来决定"这个 token 对应哪个用户"
    # 真实请求里 get_current_user 会去查 Postgres，测试里我们跳过。
    #
    # ⚠️ Header(None) 必须显式声明 —— FastAPI 用 override 函数的
    # 签名决定怎么注入参数。没 Header(None) 标注的话 FastAPI 不会
    # 从请求 header 里把 Authorization 塞进来，override 永远收到
    # None，所有带 token 的请求都会挂 401。这个 bug 静默存在过很久
    # （tests/security/test_permissions.py 里 6 个 xfail 的正主）。
    def _fake_get_current_user(authorization: str | None = Header(None)):
        from fastapi import HTTPException

        if not authorization:
            raise HTTPException(status_code=401, detail="Missing token")
        token = authorization.replace("Bearer ", "")
        from auth import decode_token

        # 真 get_current_user 把所有 decode 失败（垃圾 / 过期 / 错 secret）
        # 归一到 401；fake 也要这么做，否则 jwt.InvalidTokenError 会漏到
        # FastAPI 的 exception handler 变成 500。
        try:
            claims = decode_token(token)
        except Exception:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
            ) from None
        uid = claims["user_id"]
        users = {
            external_user["id"]: external_user,
            internal_user["id"]: internal_user,
            admin_user["id"]: admin_user,
        }
        user = users.get(uid)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    def _fake_get_optional_user(authorization: str | None = Header(None)):
        if not authorization:
            return None
        try:
            return _fake_get_current_user(authorization)
        except Exception:
            return None

    # override_dependencies 是 FastAPI 的机制：临时替换依赖
    app.dependency_overrides[get_current_user] = _fake_get_current_user
    app.dependency_overrides[get_optional_user] = _fake_get_optional_user

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    # 测试结束后清空 override，不影响其他测试
    app.dependency_overrides.clear()


# ════════════════════════════════════════════════════════════════
# 常用测试数据 fixtures
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_company_row():
    """一条完整的公司数据（含隐藏字段）"""
    return {
        "客户名称": "测试生物科技",
        "客户类型": "Biotech",
        "所处国家": "中国",
        "疾病领域": "Oncology",
        "核心产品的阶段": "Phase 2",
        # 以下是隐藏字段（外部用户看不到）
        "BD跟进优先级": "高",
        "公司质量评分": 85,
        "内部备注": "重点跟进",
        "POS预测": "60%",
    }


@pytest.fixture
def sample_asset_row():
    """一条完整的资产数据（含隐藏字段）"""
    return {
        "资产名称": "TestDrug-001",
        "所属客户": "测试生物科技",
        "临床阶段": "Phase 2",
        "疾病领域": "NSCLC",
        "靶点": "EGFR",
        # 以下是隐藏字段
        "Q总分": 78,
        "Q1_生物学": 20,
        "Q2_药物形式": 18,
        "Q3_临床监管": 22,
        "Q4_商业交易性": 18,
        "BD优先级": "P1",
        "内部备注": "Q4数据即将出来",
    }
