"""
安全测试：@public_api 边界

测什么（核心安全约束）：
    1. 合法 API Key 可以打 @public_api 标记的端点（如 /api/buyers）
    2. 合法 API Key 打未标记的端点 → 403（X-API-Key 被拒绝）
       这是防止 key 泄露后拉大损失面的关键：
       admin / write / upload / chat 等内部端点永远走不到 API key 路径
    3. 非法 API Key 打 @public_api 端点 → 401
    4. @public_api 的路由还是要 auth —— 不带任何凭证 → 401

这些约束由 auth.py 里的 _resolve_api_key_user + _route_is_public 维护。
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ════════════════════════════════════════════════════════════════
# Fixtures — 直接 TestClient + monkeypatch api_keys.verify_key
# ════════════════════════════════════════════════════════════════

VALID_KEY = "bdgo_live_" + "a" * 32
INVALID_KEY = "bdgo_live_" + "z" * 32


@pytest.fixture
def raw_client(app, external_user, monkeypatch):
    """
    TestClient + mock auth._lookup_user (让真实 get_current_user 能跑)
    + mock api_keys.verify_key (根据固定 key 返回对应 context)
    """
    import api_keys as api_keys_mod
    import auth as auth_mod
    from fastapi.testclient import TestClient

    def _fake_lookup(user_id: str):
        if user_id == external_user["id"]:
            return external_user
        from fastapi import HTTPException

        raise HTTPException(401, "User not found")

    def _fake_verify(raw_key: str, *, client_ip: str | None = None):
        if raw_key == VALID_KEY:
            return {
                "key_id": str(uuid4()),
                "user_id": external_user["id"],
                "scopes": [],
                "quota_daily": None,
            }
        return None

    monkeypatch.setattr(auth_mod, "_lookup_user", _fake_lookup)
    monkeypatch.setattr(api_keys_mod, "verify_key", _fake_verify)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def mock_crm_queries(monkeypatch):
    """
    把 crm_store.paginate / query_one 换成返回空的 mock，
    这样 @public_api 端点不会因为 CRM SQLite 缺失而 500。
    """
    import crm_store
    import services.crm.buyers as buyers_service
    import services.crm.list_view as list_view_mod

    fake_paginate = MagicMock(
        return_value={"data": [], "page": 1, "page_size": 50, "total": 0, "total_pages": 0}
    )
    fake_query_one = MagicMock(return_value=None)

    monkeypatch.setattr(crm_store, "paginate", fake_paginate)
    monkeypatch.setattr(crm_store, "query_one", fake_query_one)
    # Python import 的是符号绑定，需要在实际调用方的模块本地替换：
    #   - buyers.list_buyers 通过 list_table_view → services.crm.list_view.paginate
    #   - buyers.get_buyer → services.crm.buyers.fetch_buyer → query_one
    monkeypatch.setattr(list_view_mod, "paginate", fake_paginate)
    monkeypatch.setattr(buyers_service, "query_one", fake_query_one)


# ════════════════════════════════════════════════════════════════
# 正向：@public_api 路由接受 X-API-Key
# ════════════════════════════════════════════════════════════════


class TestApiKeyOnPublicEndpoint:
    def test_valid_key_grants_access(self, raw_client, mock_crm_queries):
        """合法 key + @public_api 端点 → 200"""
        resp = raw_client.get("/api/buyers", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200, resp.text

    def test_invalid_key_returns_401(self, raw_client, mock_crm_queries):
        """不合法的 key 即使打在 public 端点也拿不到 401"""
        resp = raw_client.get("/api/buyers", headers={"X-API-Key": INVALID_KEY})
        assert resp.status_code == 401

    def test_no_credentials_returns_401(self, raw_client, mock_crm_queries):
        """不带任何凭证 → 401（public 不等于匿名可访问）"""
        resp = raw_client.get("/api/buyers")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════
# 反向：非 @public_api 路由拒绝 X-API-Key
# ════════════════════════════════════════════════════════════════


class TestApiKeyRejectedOnPrivateEndpoint:
    """
    核心安全保证：即使 key 泄露，也不能通过它调用敏感端点。

    我们挑几个代表性的："privileged API"（/api/chat, /api/write, /api/keys 自己）。
    /api/admin 走的是 X-Admin-Key header，没走 get_current_user，不在这里测。
    """

    def test_api_key_on_chat_returns_403(self, raw_client):
        """/api/chat 不是 public → API key 应该拿不到 403"""
        resp = raw_client.post(
            "/api/chat",
            headers={"X-API-Key": VALID_KEY},
            json={"message": "hi", "session_id": "x" * 12},
        )
        assert resp.status_code == 403, (
            f"🚨 API key 居然能调 /api/chat！返回 {resp.status_code}。"
            f"这意味着 key 泄露 = MiniMax 配额暴露"
        )

    def test_api_key_on_write_returns_403(self, raw_client):
        """/api/write/* 不是 public → API key 拿不到 403"""
        resp = raw_client.put(
            "/api/write/some_table/some_pk",
            headers={"X-API-Key": VALID_KEY},
            json={"fields": {"x": "y"}},
        )
        assert resp.status_code == 403, f"🚨 API key 居然能改数据！返回 {resp.status_code}"

    def test_api_key_on_keys_router_returns_403(self, raw_client):
        """不允许 API key 自举 —— 用一个 key 创建另一个 key 就是提权"""
        resp = raw_client.post(
            "/api/keys",
            headers={"X-API-Key": VALID_KEY},
            json={"name": "bootstrapped"},
        )
        assert resp.status_code == 403, (
            f"🚨 API key 能自己创建新 key！这是提权漏洞。返回 {resp.status_code}"
        )

    def test_api_key_on_reports_returns_403(self, raw_client):
        """/api/reports/* 不是 public（要消耗 LLM credits） → API key 拿不到 403"""
        resp = raw_client.post(
            "/api/reports/generate",
            headers={"X-API-Key": VALID_KEY},
            json={"slug": "test", "params": {}},
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# 回归：@public_api 不削弱原有 JWT 鉴权
# ════════════════════════════════════════════════════════════════


class TestPublicApiDoesNotWeakenJwt:
    def test_jwt_still_works_on_public_endpoint(self, raw_client, ext_headers, mock_crm_queries):
        """同一个 @public_api 端点用 JWT 也要能过（别搞坏了网页版）"""
        resp = raw_client.get("/api/buyers", headers=ext_headers)
        assert resp.status_code == 200, resp.text

    def test_jwt_still_required_on_private_endpoint(self, raw_client):
        """没 token 的 /api/chat 还是 401（不该因为改了 auth 代码就漏过）"""
        resp = raw_client.post(
            "/api/chat",
            json={"message": "hi", "session_id": "x" * 12},
        )
        assert resp.status_code == 401
