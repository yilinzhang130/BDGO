"""
集成测试：/api/keys 路由

测什么：
    - GET  /api/keys         返回当前用户的 keys（不带 hash）
    - POST /api/keys         创建 key，返回原文 + 脱敏记录
    - DELETE /api/keys/{id}  吊销 key
    - 无 token 时返回 401

Auth 通过 monkeypatch auth._lookup_user 替换（绕过 DB 查询）。
api_keys 的 DB 操作也通过 monkeypatch 替换。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ════════════════════════════════════════════════════════════════
# 本文件专用 fixture：直接用 TestClient，不走 conftest.client
# 绕开 conftest 里 fake 没 Header() 的问题
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def raw_client(app, external_user, monkeypatch):
    """
    TestClient + mock 掉 auth._lookup_user，这样真实的 get_current_user
    可以跑通 JWT 解码流程，只是不连 Postgres。
    """
    import auth as auth_mod
    from fastapi.testclient import TestClient

    def _fake_lookup(user_id: str):
        if user_id == external_user["id"]:
            return external_user
        from fastapi import HTTPException

        raise HTTPException(401, "User not found")

    monkeypatch.setattr(auth_mod, "_lookup_user", _fake_lookup)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def install_mock_db(monkeypatch):
    """
    返回一个函数，用于安装带给定 cursor 的 mock auth_db.transaction。
    caller 先准备好 cursor.fetchone/fetchall 的 return_value/side_effect，
    然后调用这个函数把它挂到 api_keys.auth_db.transaction 上。
    """
    import api_keys as api_keys_mod

    def _install(cursor: MagicMock):
        class _FakeTx:
            def __enter__(self):
                return cursor

            def __exit__(self, *_):
                return False

        monkeypatch.setattr(api_keys_mod.auth_db, "transaction", lambda: _FakeTx())

    return _install


# ════════════════════════════════════════════════════════════════
# GET /api/keys
# ════════════════════════════════════════════════════════════════


class TestListKeys:
    def test_requires_jwt(self, raw_client):
        """无 token → 401"""
        resp = raw_client.get("/api/keys")
        assert resp.status_code == 401

    def test_empty_list(self, raw_client, ext_headers, install_mock_db):
        """没有 key 时返回 items: []"""
        cur = MagicMock()
        cur.fetchall.return_value = []
        install_mock_db(cur)

        resp = raw_client.get("/api/keys", headers=ext_headers)
        assert resp.status_code == 200
        assert resp.json() == {"items": []}

    def test_list_excludes_key_hash(self, raw_client, ext_headers, install_mock_db):
        """🚨 安全：响应里绝不包含 key_hash"""
        cur = MagicMock()
        cur.fetchall.return_value = [
            {
                "id": uuid4(),
                "user_id": uuid4(),
                "name": "my-script",
                "key_prefix": "bdgo_live_ab12",
                "key_hash": "DEADBEEF" * 8,
                "scopes": [],
                "quota_daily": None,
                "created_at": datetime(2026, 4, 22, 12, 0, 0),
                "last_used_at": None,
                "last_used_ip": None,
                "revoked_at": None,
                "expires_at": None,
            }
        ]
        install_mock_db(cur)

        resp = raw_client.get("/api/keys", headers=ext_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert "key_hash" not in item, "🚨 API 泄露了 key_hash"
        assert item["key_prefix"] == "bdgo_live_ab12"
        assert item["is_active"] is True


# ════════════════════════════════════════════════════════════════
# POST /api/keys — 创建
# ════════════════════════════════════════════════════════════════


class TestCreateKey:
    def test_requires_jwt(self, raw_client):
        resp = raw_client.post("/api/keys", json={"name": "test"})
        assert resp.status_code == 401

    def test_missing_name_returns_422(self, raw_client, ext_headers):
        resp = raw_client.post("/api/keys", headers=ext_headers, json={})
        assert resp.status_code == 422

    def test_overlong_name_returns_422(self, raw_client, ext_headers):
        resp = raw_client.post(
            "/api/keys",
            headers=ext_headers,
            json={"name": "x" * 101},
        )
        assert resp.status_code == 422

    def test_returns_secret_and_record(self, raw_client, ext_headers, install_mock_db):
        """成功创建 → 返回 {key: bdgo_live_..., record: {...}}"""
        from api_keys import KEY_LENGTH, KEY_PREFIX

        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"n": 0},  # active count
            {  # INSERT RETURNING
                "id": uuid4(),
                "user_id": uuid4(),
                "name": "my-script",
                "key_prefix": "bdgo_live_ab12",
                "scopes": [],
                "quota_daily": None,
                "created_at": datetime(2026, 4, 22, 12, 0, 0),
                "last_used_at": None,
                "revoked_at": None,
                "expires_at": None,
            },
        ]
        install_mock_db(cur)

        resp = raw_client.post("/api/keys", headers=ext_headers, json={"name": "my-script"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["key"].startswith(KEY_PREFIX)
        assert len(body["key"]) == KEY_LENGTH
        assert "key_hash" not in body["record"], "🚨 POST 响应泄露 key_hash"
        assert body["record"]["name"] == "my-script"


# ════════════════════════════════════════════════════════════════
# Revoke endpoint — DELETE on /api/keys/<id>
# ════════════════════════════════════════════════════════════════


class TestRevokeKey:
    def test_requires_jwt(self, raw_client):
        resp = raw_client.delete(f"/api/keys/{uuid4()}")
        assert resp.status_code == 401

    def test_not_found_returns_404(self, raw_client, ext_headers, install_mock_db):
        cur = MagicMock()
        cur.fetchone.return_value = None  # UPDATE matched 0 rows
        install_mock_db(cur)

        resp = raw_client.delete(f"/api/keys/{uuid4()}", headers=ext_headers)
        assert resp.status_code == 404

    def test_success_returns_record(self, raw_client, ext_headers, install_mock_db):
        kid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {
            "id": kid,
            "user_id": uuid4(),
            "name": "stale-key",
            "key_prefix": "bdgo_live_oldk",
            "scopes": [],
            "quota_daily": None,
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
            "last_used_at": None,
            "revoked_at": datetime(2026, 4, 22, 12, 0, 0),
            "expires_at": None,
        }
        install_mock_db(cur)

        resp = raw_client.delete(f"/api/keys/{kid}", headers=ext_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_active"] is False
        assert "key_hash" not in body
