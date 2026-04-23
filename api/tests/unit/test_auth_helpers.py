"""
单元测试：auth.py 里的 JWT 工具函数

测什么：
    - create_token / decode_token 正常工作
    - token 过期后被拒绝
    - 用错误 secret 签的 token 被拒绝
    - 密码 hash/verify 正确
"""

import datetime
import time

import config
import jwt
import pytest
from auth import create_token, decode_token, hash_password, verify_password

# ════════════════════════════════════════════════════════════════
# JWT create / decode
# ════════════════════════════════════════════════════════════════


class TestJWT:
    def test_create_and_decode_roundtrip(self):
        """创建 token 后能正确解码"""
        token = create_token("user-123", "test@example.com")
        claims = decode_token(token)
        assert claims["user_id"] == "user-123"
        assert claims["email"] == "test@example.com"

    def test_token_contains_expiry(self):
        """token 里有 exp 字段"""
        token = create_token("user-123", "test@example.com")
        # 不验签，只看结构
        raw = jwt.decode(token, options={"verify_signature": False})
        assert "exp" in raw
        # exp 在未来
        assert raw["exp"] > time.time()

    def test_expired_token_rejected(self):
        """过期 token 被拒绝"""
        # 手动造一个已过期的 token
        payload = {
            "user_id": "user-123",
            "email": "test@example.com",
            "exp": datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1),
        }
        expired_token = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(expired_token)

    def test_wrong_secret_rejected(self):
        """用不同 secret 签的 token 被拒绝"""
        payload = {
            "user_id": "user-123",
            "email": "test@example.com",
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1),
        }
        evil_token = jwt.encode(payload, "completely-wrong-secret", algorithm="HS256")

        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(evil_token)

    def test_tampered_token_rejected(self):
        """手动篡改 payload 后 token 无效"""
        token = create_token("user-123", "test@example.com")
        # token 格式是 header.payload.signature，篡改 payload
        parts = token.split(".")
        import base64
        import json

        fake_payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {"user_id": "admin-000", "email": "hacker@evil.com", "exp": time.time() + 86400}
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
        tampered = f"{parts[0]}.{fake_payload}.{parts[2]}"

        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(tampered)

    def test_garbage_string_rejected(self):
        """完全无效的字符串被拒绝"""
        with pytest.raises(Exception):
            decode_token("not.a.jwt.at.all")

    def test_empty_string_rejected(self):
        with pytest.raises(Exception):
            decode_token("")


# ════════════════════════════════════════════════════════════════
# 密码 hash / verify
# ════════════════════════════════════════════════════════════════


class TestPassword:
    def test_hash_and_verify(self):
        """正确密码能验证通过"""
        hashed = hash_password("MySecurePassword123")
        assert verify_password("MySecurePassword123", hashed) is True

    def test_wrong_password_fails(self):
        """错误密码验证失败"""
        hashed = hash_password("CorrectPassword")
        assert verify_password("WrongPassword", hashed) is False

    def test_hash_is_not_plaintext(self):
        """hash 不是明文"""
        pwd = "plaintext123"
        hashed = hash_password(pwd)
        assert hashed != pwd
        assert len(hashed) > 20

    def test_same_password_different_hashes(self):
        """同一密码每次 hash 不同（bcrypt 加盐）"""
        pwd = "samepassword"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        assert h1 != h2
        # 但两个 hash 都能验证成功
        assert verify_password(pwd, h1) is True
        assert verify_password(pwd, h2) is True


# ════════════════════════════════════════════════════════════════
# JWT_SECRET 配置检查
# ════════════════════════════════════════════════════════════════


class TestJWTSecretConfig:
    def test_jwt_secret_is_set(self):
        """JWT_SECRET 不能为空"""
        assert config.JWT_SECRET, "JWT_SECRET 不能为空字符串"

    def test_jwt_secret_not_known_bad_value(self):
        """确保没有用已知的不安全默认值"""
        bad_secrets = [
            "dev-secret-DO-NOT-USE-IN-PRODUCTION",
            "secret",
            "changeme",
            "password",
            "12345678",
        ]
        assert config.JWT_SECRET not in bad_secrets, (
            f"JWT_SECRET 使用了已知的不安全默认值: {config.JWT_SECRET}"
        )

    def test_jwt_secret_minimum_length(self):
        """JWT_SECRET 长度至少 32 字符"""
        assert len(config.JWT_SECRET) >= 32, (
            f"JWT_SECRET 太短（{len(config.JWT_SECRET)} 字符），建议至少 32 字符"
        )
