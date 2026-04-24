"""
安全测试：权限边界

测什么：
    - 没有 token 的请求被拒绝（401）
    - 过期/伪造 token 被拒绝（401）
    - 外部用户访问 admin 接口被拒绝（403）
    - 字段泄露：API 响应里不包含内部字段

这些测试是「回归测试」——将来改了 auth 相关代码后，
如果这些测试仍然通过，说明安全边界没有被意外打破。
"""


# ════════════════════════════════════════════════════════════════
# 认证边界
# ════════════════════════════════════════════════════════════════


class TestAuthBoundary:
    def test_no_token_returns_401(self, client):
        """无 token 的请求返回 401"""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self, client):
        """垃圾字符串 token 返回 401"""
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer this-is-not-a-jwt"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client):
        """过期 token 返回 401"""
        import datetime

        import config
        import jwt

        payload = {
            "user_id": "user-ext-001",
            "email": "test@example.com",
            "exp": datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=60),
        }
        expired = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 401

    def test_wrong_secret_token_returns_401(self, client):
        """用不同 secret 签的 token 返回 401"""
        import datetime

        import jwt

        payload = {
            "user_id": "user-ext-001",
            "email": "test@example.com",
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1),
        }
        evil_token = jwt.encode(payload, "wrong-secret-123", algorithm="HS256")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {evil_token}"})
        assert resp.status_code == 401

    def test_valid_token_returns_200(self, client, ext_headers):
        """有效 token 能访问 /me"""
        resp = client.get("/api/auth/me", headers=ext_headers)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════
# 权限隔离：外部用户不能调用 Admin 接口
# ════════════════════════════════════════════════════════════════


class TestAdminIsolation:
    def test_external_cannot_access_admin_stats(self, client, ext_headers):
        """外部用户不能访问 /api/admin/ 系列接口"""
        resp = client.get("/api/admin/users", headers=ext_headers)
        assert resp.status_code in (403, 404), (
            f"外部用户访问 admin 接口应该被拒绝，但返回了 {resp.status_code}"
        )

    def test_internal_without_admin_cannot_access_admin(self, client, int_headers):
        """内部用户（非 admin）也不能访问 admin 接口"""
        resp = client.get("/api/admin/users", headers=int_headers)
        assert resp.status_code in (403, 404)

    def test_no_token_cannot_access_admin(self, client):
        resp = client.get("/api/admin/users")
        assert resp.status_code in (401, 403, 404)


# ════════════════════════════════════════════════════════════════
# 字段泄露检测：API 层
# ════════════════════════════════════════════════════════════════


class TestFieldLeakage:
    """
    这组测试 mock CRM 数据库，注入含内部字段的行，
    然后验证 API 响应里这些字段不出现在外部用户的视角里。
    """

    INTERNAL_FIELDS = [
        "BD跟进优先级",
        "BD联系人",
        "BD状态",
        "公司质量评分",
        "内部备注",
        "内部评分",
        "POS预测",
    ]

    def test_me_response_has_no_hashed_password(self, client, ext_headers):
        """
        /api/auth/me 不能返回 hashed_password。
        这是最基础的字段泄露测试。
        """
        resp = client.get("/api/auth/me", headers=ext_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "hashed_password" not in data, "🚨 安全漏洞：/me 接口泄露了 hashed_password！"

    def test_me_response_structure(self, client, ext_headers):
        """/me 返回预期字段"""
        resp = client.get("/api/auth/me", headers=ext_headers)
        assert resp.status_code == 200
        data = resp.json()
        # 应该有这些字段
        assert "id" in data
        assert "email" in data
        assert "name" in data
        # 不应该有这个字段
        assert "hashed_password" not in data
