"""
单元测试：api_keys.py 里的纯逻辑

测什么：
    - Key 格式：bdgo_live_<32-char-base62>，46 字符
    - Hash 确定性：同样的 key 产生同样的 sha256
    - 序列化：key_hash 永远不会泄露到返回 dict
    - 参数校验：空名字、超长名字、非法 quota
    - Key 上限：第 11 个 active key 被拒绝

DB 操作用 monkeypatch 替换 auth_db.transaction，不依赖真实 Postgres。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

# ════════════════════════════════════════════════════════════════
# Key 格式 & hash
# ════════════════════════════════════════════════════════════════


class TestKeyGeneration:
    def test_format_is_bdgo_live_prefix(self):
        """生成的 key 以 bdgo_live_ 开头"""
        from api_keys import _generate_key

        k = _generate_key()
        assert k.startswith("bdgo_live_")

    def test_format_total_length(self):
        """完整长度 = 'bdgo_live_' (10) + 32 字符 body = 42"""
        from api_keys import _generate_key

        k = _generate_key()
        assert len(k) == 42, f"Expected 42, got {len(k)}: {k!r}"

    def test_body_is_base62(self):
        """Body 只能是 a-zA-Z0-9"""
        import re

        from api_keys import _generate_key

        k = _generate_key()
        body = k.removeprefix("bdgo_live_")
        assert re.fullmatch(r"[a-zA-Z0-9]{32}", body), f"Bad body: {body}"

    def test_each_call_produces_unique_key(self):
        """连续生成的 key 不会重复（熵足够）"""
        from api_keys import _generate_key

        keys = {_generate_key() for _ in range(50)}
        assert len(keys) == 50

    def test_custom_env_tag(self):
        """支持 test 环境 tag（预留未来沙盒）"""
        from api_keys import _generate_key

        k = _generate_key(env="test")
        assert k.startswith("bdgo_test_")


class TestKeyHash:
    def test_hash_is_deterministic(self):
        """同样的输入产生同样的 hash"""
        from api_keys import _hash_key

        a = _hash_key("bdgo_live_abc")
        b = _hash_key("bdgo_live_abc")
        assert a == b

    def test_hash_is_sha256_hex(self):
        """返回 64 字符 hex（sha256 长度）"""
        import re

        from api_keys import _hash_key

        h = _hash_key("bdgo_live_xyz")
        assert re.fullmatch(r"[0-9a-f]{64}", h)

    def test_different_inputs_different_hashes(self):
        from api_keys import _hash_key

        assert _hash_key("bdgo_live_a") != _hash_key("bdgo_live_b")


# ════════════════════════════════════════════════════════════════
# 序列化 — 确保 hash 永远不泄露
# ════════════════════════════════════════════════════════════════


class TestSerialize:
    def _make_row(self, **over):
        base = {
            "id": uuid4(),
            "user_id": uuid4(),
            "name": "test",
            "key_prefix": "bdgo_live_abcd",
            "key_hash": "DEADBEEF" * 8,  # 64 chars
            "scopes": [],
            "quota_daily": None,
            "created_at": datetime(2026, 4, 22, 12, 0, 0),
            "last_used_at": None,
            "revoked_at": None,
            "expires_at": None,
            "last_used_ip": None,
        }
        base.update(over)
        return base

    def test_hash_never_surfaces(self):
        """🚨 安全：key_hash 必须从返回 dict 里剥掉"""
        from api_keys import _serialize_row

        row = self._make_row()
        out = _serialize_row(row)
        assert "key_hash" not in out, "🚨 API 泄露了 key_hash！"

    def test_uuids_stringified(self):
        """UUID 转成字符串以便 JSON 序列化"""
        from api_keys import _serialize_row

        row = self._make_row()
        out = _serialize_row(row)
        assert isinstance(out["id"], str)
        assert isinstance(out["user_id"], str)
        UUID(out["id"])  # 如果不是合法 UUID 会抛
        UUID(out["user_id"])

    def test_timestamps_iso_format(self):
        """timestamp 转 ISO 字符串"""
        from api_keys import _serialize_row

        row = self._make_row(last_used_at=datetime(2026, 4, 22, 14, 30, 0))
        out = _serialize_row(row)
        assert out["created_at"] == "2026-04-22T12:00:00"
        assert out["last_used_at"] == "2026-04-22T14:30:00"

    def test_is_active_when_no_revoke_no_expiry(self):
        from api_keys import _serialize_row

        row = self._make_row()
        out = _serialize_row(row)
        assert out["is_active"] is True

    def test_is_active_false_when_revoked(self):
        from api_keys import _serialize_row

        row = self._make_row(revoked_at=datetime(2026, 4, 22))
        out = _serialize_row(row)
        assert out["is_active"] is False

    def test_is_active_false_when_expired(self):
        """expires_at in the past → is_active=False (regression: prior impl
        re-parsed the just-stringified ISO timestamp and would TypeError if
        the column ever became TIMESTAMPTZ)."""
        from api_keys import _serialize_row

        row = self._make_row(expires_at=datetime(2020, 1, 1))
        out = _serialize_row(row)
        assert out["is_active"] is False

    def test_is_active_true_when_expiry_in_future(self):
        from api_keys import _serialize_row

        row = self._make_row(expires_at=datetime(2099, 1, 1))
        out = _serialize_row(row)
        assert out["is_active"] is True


# ════════════════════════════════════════════════════════════════
# create_key — 参数校验
# ════════════════════════════════════════════════════════════════


class TestCreateKeyValidation:
    """
    不碰 DB，只测 create_key 的早期参数校验分支。
    注入 mock cursor，fetchone 返回"0 active keys"，足够让调用走到 INSERT 前。
    """

    def _mock_db(self, active_count=0):
        """Cursor whose fetchone yields (active-count check, INSERT RETURNING)."""
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {"n": active_count},
            {
                "id": uuid4(),
                "user_id": uuid4(),
                "name": "t",
                "key_prefix": "bdgo_live_ab",
                "scopes": [],
                "quota_daily": None,
                "created_at": datetime(2026, 4, 22, 12, 0, 0),
                "last_used_at": None,
                "revoked_at": None,
                "expires_at": None,
            },
        ]
        return mock_cur

    def test_empty_name_rejected(self):
        from api_keys import create_key

        with pytest.raises(HTTPException) as exc:
            create_key(user_id=str(uuid4()), name="")
        assert exc.value.status_code == 400
        assert "名称" in exc.value.detail

    def test_whitespace_only_name_rejected(self):
        from api_keys import create_key

        with pytest.raises(HTTPException) as exc:
            create_key(user_id=str(uuid4()), name="   ")
        assert exc.value.status_code == 400

    def test_overlong_name_rejected(self):
        from api_keys import create_key

        with pytest.raises(HTTPException) as exc:
            create_key(user_id=str(uuid4()), name="x" * 200)
        assert exc.value.status_code == 400

    def test_zero_quota_rejected(self):
        from api_keys import create_key

        with pytest.raises(HTTPException) as exc:
            create_key(user_id=str(uuid4()), name="ok", quota_daily=0)
        assert exc.value.status_code == 400

    def test_negative_quota_rejected(self):
        from api_keys import create_key

        with pytest.raises(HTTPException) as exc:
            create_key(user_id=str(uuid4()), name="ok", quota_daily=-1)
        assert exc.value.status_code == 400

    def test_max_active_keys_enforced(self):
        """用户已有 MAX_ACTIVE_KEYS_PER_USER 个 key 时，创建被拒"""
        from api_keys import MAX_ACTIVE_KEYS_PER_USER, create_key

        mock_cur = MagicMock()
        # fetchone 返回已达上限
        mock_cur.fetchone.return_value = {"n": MAX_ACTIVE_KEYS_PER_USER}

        with patch("api_keys.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(HTTPException) as exc:
                create_key(user_id=str(uuid4()), name="valid")

        assert exc.value.status_code == 400
        assert str(MAX_ACTIVE_KEYS_PER_USER) in exc.value.detail

    def test_create_key_returns_raw_key_and_record(self):
        """成功路径：返回 dict 里有 key (原文) 和 record (脱敏)"""
        from api_keys import create_key

        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {"n": 0},  # count check
            {  # INSERT RETURNING
                "id": uuid4(),
                "user_id": uuid4(),
                "name": "ok",
                "key_prefix": "bdgo_live_ab",
                "scopes": [],
                "quota_daily": None,
                "created_at": datetime(2026, 4, 22, 12, 0, 0),
                "last_used_at": None,
                "revoked_at": None,
                "expires_at": None,
            },
        ]

        with patch("api_keys.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            out = create_key(user_id=str(uuid4()), name="ok")

        assert "key" in out
        assert out["key"].startswith("bdgo_live_")
        assert "record" in out
        assert "key_hash" not in out["record"], "🚨 record 泄露了 key_hash"


# ════════════════════════════════════════════════════════════════
# verify_key — prefix / expiry 校验
# ════════════════════════════════════════════════════════════════


class TestVerifyKey:
    def test_empty_returns_none(self):
        from api_keys import verify_key

        assert verify_key("") is None

    def test_none_returns_none(self):
        from api_keys import verify_key

        assert verify_key(None) is None

    def test_wrong_prefix_returns_none_without_db(self):
        """非 bdgo_ 开头的 key 直接拒绝，不该打 DB"""
        from api_keys import verify_key

        with patch("api_keys.auth_db.transaction") as mock_tx:
            result = verify_key("sk-not-our-key")
        assert result is None
        assert mock_tx.call_count == 0, "不合法前缀不该打 DB"

    def test_unknown_key_returns_none(self):
        """bdgo_ 前缀但 DB 查不到 → None"""
        from api_keys import verify_key

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None

        with patch("api_keys.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            assert verify_key("bdgo_live_fake_key_nonexistent") is None

    def test_expired_key_returns_none(self):
        """过期时间早于现在 → None"""
        from api_keys import verify_key

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {
            "id": uuid4(),
            "user_id": uuid4(),
            "scopes": [],
            "quota_daily": None,
            "expires_at": datetime(2020, 1, 1),  # 早已过期
        }

        with patch("api_keys.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            assert verify_key("bdgo_live_" + "a" * 32) is None

    def test_valid_key_returns_context(self):
        """有效 key → 返回 {key_id, user_id, scopes, quota_daily}"""
        from api_keys import verify_key

        kid = uuid4()
        uid = uuid4()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {
            "id": kid,
            "user_id": uid,
            "scopes": ["read:companies"],
            "quota_daily": 1000,
            "expires_at": None,
        }

        with patch("api_keys.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            ctx = verify_key("bdgo_live_" + "b" * 32)

        assert ctx is not None
        assert ctx["key_id"] == str(kid)
        assert ctx["user_id"] == str(uid)
        assert ctx["scopes"] == ["read:companies"]
        assert ctx["quota_daily"] == 1000


# ════════════════════════════════════════════════════════════════
# revoke_key
# ════════════════════════════════════════════════════════════════


class TestRevokeKey:
    def test_not_found_raises_404(self):
        """别人的 key / 已吊销 / 不存在都返回 404"""
        from api_keys import revoke_key

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None  # UPDATE 返回 0 行

        with patch("api_keys.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(HTTPException) as exc:
                revoke_key(user_id=str(uuid4()), key_id=str(uuid4()))

        assert exc.value.status_code == 404

    def test_scoped_to_owner_sql_has_user_id_filter(self):
        """🚨 安全：UPDATE 必须同时按 user_id + id 过滤，防越权"""
        import inspect

        from api_keys import revoke_key

        src = inspect.getsource(revoke_key)
        # 要求 WHERE 子句里同时有 id 和 user_id
        assert "user_id" in src.lower()
        assert "id = %s" in src or "id=%s" in src.replace(" ", "")
