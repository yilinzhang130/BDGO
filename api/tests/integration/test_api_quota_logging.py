"""
集成测试：API key 配额 + 请求日志

测什么：
    - 有 quota_daily 的 key 在调用次数达到配额时被 429 阻止
    - quota_daily=None 的 key 不限流
    - 每次 API key 调用都产出一条 api_request_logs 记录
    - JWT 调用不产生 api_request_logs 记录（该表只记外部 key 流量）
    - log_request 异常被吞掉，不影响请求成功
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

VALID_KEY_WITH_QUOTA = "bdgo_live_" + "q" * 32
VALID_KEY_UNLIMITED = "bdgo_live_" + "u" * 32


@pytest.fixture
def raw_client(app, external_user, monkeypatch):
    """同前 — 完整 TestClient + mock _lookup_user + mock verify_key"""
    import api_keys as api_keys_mod
    import auth as auth_mod
    from fastapi.testclient import TestClient

    QUOTA_KEY_ID = str(uuid4())
    UNLIMITED_KEY_ID = str(uuid4())

    def _fake_lookup(user_id: str):
        if user_id == external_user["id"]:
            return external_user
        from fastapi import HTTPException

        raise HTTPException(401, "not found")

    def _fake_verify(raw_key: str, *, client_ip: str | None = None):
        if raw_key == VALID_KEY_WITH_QUOTA:
            return {
                "key_id": QUOTA_KEY_ID,
                "user_id": external_user["id"],
                "scopes": [],
                "quota_daily": 3,
            }
        if raw_key == VALID_KEY_UNLIMITED:
            return {
                "key_id": UNLIMITED_KEY_ID,
                "user_id": external_user["id"],
                "scopes": [],
                "quota_daily": None,
            }
        return None

    monkeypatch.setattr(auth_mod, "_lookup_user", _fake_lookup)
    monkeypatch.setattr(api_keys_mod, "verify_key", _fake_verify)

    with TestClient(app, raise_server_exceptions=False) as c:
        # expose key-id constants for assertions
        c._quota_key_id = QUOTA_KEY_ID
        c._unlimited_key_id = UNLIMITED_KEY_ID
        yield c


@pytest.fixture
def mock_crm_queries(monkeypatch):
    """Mock CRM so /api/buyers doesn't blow up on missing SQLite."""
    import crm_store
    import routers.buyers as buyers_router
    import services.crm.list_view as list_view_mod

    fake_paginate = MagicMock(
        return_value={"data": [], "page": 1, "page_size": 50, "total": 0, "total_pages": 0}
    )
    fake_query_one = MagicMock(return_value=None)
    monkeypatch.setattr(crm_store, "paginate", fake_paginate)
    monkeypatch.setattr(crm_store, "query_one", fake_query_one)
    # list_buyers now calls list_table_view → services.crm.list_view.paginate
    # (buyers.py itself no longer imports paginate after S-004)
    monkeypatch.setattr(list_view_mod, "paginate", fake_paginate)
    monkeypatch.setattr(buyers_router, "query_one", fake_query_one)


# ════════════════════════════════════════════════════════════════
# 配额
# ════════════════════════════════════════════════════════════════


class TestDailyQuota:
    def test_under_quota_allowed(self, raw_client, mock_crm_queries, monkeypatch):
        """配额 3、已用 2 → 放行"""
        import api_request_log as arl

        monkeypatch.setattr(arl, "count_today", lambda _kid: 2)
        # log_request 的 no-op stub（不连真 DB）
        monkeypatch.setattr(arl, "log_request", lambda **kw: None)

        resp = raw_client.get(
            "/api/buyers",
            headers={"X-API-Key": VALID_KEY_WITH_QUOTA},
        )
        assert resp.status_code == 200

    def test_at_quota_blocked_429(self, raw_client, mock_crm_queries, monkeypatch):
        """配额 3、已用 3 → 429"""
        import api_request_log as arl

        monkeypatch.setattr(arl, "count_today", lambda _kid: 3)
        monkeypatch.setattr(arl, "log_request", lambda **kw: None)

        resp = raw_client.get(
            "/api/buyers",
            headers={"X-API-Key": VALID_KEY_WITH_QUOTA},
        )
        assert resp.status_code == 429
        assert "配额" in resp.json()["detail"]

    def test_over_quota_blocked_429(self, raw_client, mock_crm_queries, monkeypatch):
        """已用超过配额 → 429（防御性边界）"""
        import api_request_log as arl

        monkeypatch.setattr(arl, "count_today", lambda _kid: 999_999)
        monkeypatch.setattr(arl, "log_request", lambda **kw: None)

        resp = raw_client.get(
            "/api/buyers",
            headers={"X-API-Key": VALID_KEY_WITH_QUOTA},
        )
        assert resp.status_code == 429

    def test_null_quota_unlimited(self, raw_client, mock_crm_queries, monkeypatch):
        """quota_daily=None 的 key 不该触发配额检查（也不该打 count_today）"""
        import api_request_log as arl

        count_called = {"n": 0}

        def _spy(_kid):
            count_called["n"] += 1
            return 1_000_000  # even huge number shouldn't matter

        monkeypatch.setattr(arl, "count_today", _spy)
        monkeypatch.setattr(arl, "log_request", lambda **kw: None)

        resp = raw_client.get(
            "/api/buyers",
            headers={"X-API-Key": VALID_KEY_UNLIMITED},
        )
        assert resp.status_code == 200
        assert count_called["n"] == 0, "quota_daily=None 时不该查 count_today"


# ════════════════════════════════════════════════════════════════
# 日志写入
# ════════════════════════════════════════════════════════════════


class TestRequestLogging:
    def test_api_key_call_writes_log(self, raw_client, mock_crm_queries, monkeypatch):
        """每次 API key 成功调用都要写一条 log 行"""
        import api_request_log as arl

        captured: list[dict] = []
        monkeypatch.setattr(arl, "count_today", lambda _kid: 0)
        monkeypatch.setattr(
            arl,
            "log_request",
            lambda **kw: captured.append(kw),
        )

        resp = raw_client.get(
            "/api/buyers?q=test",
            headers={"X-API-Key": VALID_KEY_UNLIMITED},
        )
        assert resp.status_code == 200
        assert len(captured) == 1
        row = captured[0]
        assert row["key_id"] == raw_client._unlimited_key_id
        assert row["user_id"] is not None
        assert row["method"] == "GET"
        assert row["path"] == "/api/buyers"  # query string stripped
        assert row["status"] == 200
        assert isinstance(row["latency_ms"], int)
        assert row["latency_ms"] >= 0

    def test_jwt_call_does_not_write_log(
        self, raw_client, ext_headers, mock_crm_queries, monkeypatch
    ):
        """JWT 流量不该进 api_request_logs（只记外部 key）"""
        import api_request_log as arl

        captured: list[dict] = []
        monkeypatch.setattr(arl, "log_request", lambda **kw: captured.append(kw))

        resp = raw_client.get("/api/buyers", headers=ext_headers)
        assert resp.status_code == 200
        assert captured == [], "JWT 流量漏进了 api_request_logs"

    def test_logging_failure_does_not_break_request(
        self, raw_client, mock_crm_queries, monkeypatch
    ):
        """log_request 抛异常 → 请求仍然 200（可用性高于审计完整性）"""
        import api_request_log as arl

        monkeypatch.setattr(arl, "count_today", lambda _kid: 0)

        def _boom(**kw):
            raise RuntimeError("DB connection lost")

        monkeypatch.setattr(arl, "log_request", _boom)

        resp = raw_client.get(
            "/api/buyers",
            headers={"X-API-Key": VALID_KEY_UNLIMITED},
        )
        assert resp.status_code == 200, f"日志写入失败不该阻塞请求。返回 {resp.status_code}"

    def test_failed_request_still_logged(self, raw_client, mock_crm_queries, monkeypatch):
        """4xx/5xx 响应也要进 log（便于错误率监控）"""
        import api_request_log as arl

        captured: list[dict] = []
        monkeypatch.setattr(arl, "count_today", lambda _kid: 0)
        monkeypatch.setattr(arl, "log_request", lambda **kw: captured.append(kw))

        # 这个路径不存在 → 404
        resp = raw_client.get(
            "/api/buyers/nonexistent-ZZZZZZ",
            headers={"X-API-Key": VALID_KEY_UNLIMITED},
        )
        # mock_query_one 返回 None → 404
        assert resp.status_code == 404
        assert len(captured) == 1
        assert captured[0]["status"] == 404


# ════════════════════════════════════════════════════════════════
# count_today 纯函数单测
# ════════════════════════════════════════════════════════════════


class TestCountToday:
    def test_returns_zero_on_db_error(self, monkeypatch):
        """DB 挂了时 count_today 返回 0（fail-open）"""
        import api_request_log as arl

        def _boom():
            raise RuntimeError("DB down")

        monkeypatch.setattr(arl.auth_db, "transaction", _boom)

        assert arl.count_today("any-key-id") == 0

    def test_returns_count_from_row(self, monkeypatch):
        import api_request_log as arl

        cur = MagicMock()
        cur.fetchone.return_value = {"n": 42}

        class _Tx:
            def __enter__(self):
                return cur

            def __exit__(self, *_):
                return False

        monkeypatch.setattr(arl.auth_db, "transaction", lambda: _Tx())
        assert arl.count_today("kid") == 42
