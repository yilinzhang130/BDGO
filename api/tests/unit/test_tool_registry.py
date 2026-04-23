"""
单元测试：工具注册系统（registry.py + __init__.py）

测什么：
    - 所有工具都被正确注册（没有拼写错误导致的漏注册）
    - execute_tool 对未知工具名返回 error
    - execute_tool 字段过滤对外部用户生效
    - count_by 对隐藏字段拒绝外部用户
    - user_id 只注入到声明了 NEEDS_USER_ID 的工具
"""

import json

# ════════════════════════════════════════════════════════════════
# 工具注册完整性检查
# ════════════════════════════════════════════════════════════════


class TestToolRegistration:
    def test_all_schemas_have_impl(self):
        """每个 SCHEMA 都有对应的 IMPL 函数"""
        from routers.chat.tools import TOOL_IMPL, TOOLS

        for schema in TOOLS:
            name = schema["name"]
            assert name in TOOL_IMPL, f"工具 '{name}' 在 SCHEMAS 里有定义，但在 IMPLS 里找不到实现"

    def test_all_impls_have_schema(self):
        """每个 IMPL 函数都有对应的 SCHEMA 描述"""
        from routers.chat.tools import TOOL_IMPL, TOOLS

        schema_names = {s["name"] for s in TOOLS}
        for name in TOOL_IMPL:
            assert name in schema_names, f"工具 '{name}' 有实现函数，但没有 SCHEMA（LLM 看不到它）"

    def test_all_schemas_have_required_fields(self):
        """每个 SCHEMA 都有 name, description, input_schema"""
        from routers.chat.tools import TOOLS

        for schema in TOOLS:
            assert "name" in schema, f"schema 缺少 'name': {schema}"
            assert "description" in schema, f"工具 '{schema.get('name')}' 缺少 description"
            assert "input_schema" in schema, f"工具 '{schema.get('name')}' 缺少 input_schema"

    def test_crm_tools_are_registered(self):
        """核心 CRM 工具都存在"""
        from routers.chat.tools import TOOL_IMPL

        required_tools = [
            "search_companies",
            "get_company",
            "search_assets",
            "get_asset",
            "search_deals",
            "search_clinical",
            "buyer_match",
            "search_global",
        ]
        for tool in required_tools:
            assert tool in TOOL_IMPL, f"核心工具 '{tool}' 未注册"

    def test_tool_table_covers_crm_tools(self):
        """TOOL_TABLE 覆盖了需要字段过滤的 CRM 工具"""
        from routers.chat.tools.registry import TOOL_TABLE

        expected = [
            "search_companies",
            "get_company",
            "search_assets",
            "get_asset",
            "search_clinical",
            "search_deals",
        ]
        for tool in expected:
            assert tool in TOOL_TABLE, f"工具 '{tool}' 未在 TOOL_TABLE 中声明字段映射"

    def test_needs_user_id_declared(self):
        """关键工具声明了需要 user_id"""
        from routers.chat.tools.registry import NEEDS_USER_ID

        assert "add_to_watchlist" in NEEDS_USER_ID


# ════════════════════════════════════════════════════════════════
# execute_tool 分发逻辑
# ════════════════════════════════════════════════════════════════


class TestExecuteTool:
    def test_unknown_tool_returns_error(self):
        """未知工具名返回 error JSON"""
        from routers.chat.tools.registry import execute_tool

        result = json.loads(execute_tool({}, "nonexistent_tool", {}))
        assert "error" in result

    def test_tool_exception_returns_error_with_sentinel(self):
        """工具抛异常时返回带 _tool_failed 标志的 JSON"""
        from routers.chat.tools.registry import TOOL_FAILED_KEY, execute_tool

        def boom(**kwargs):
            raise ValueError("模拟工具崩溃")

        impls = {"broken_tool": boom}
        result = json.loads(execute_tool(impls, "broken_tool", {}))
        assert "error" in result
        assert result.get(TOOL_FAILED_KEY) is True

    def test_tool_result_truncated_at_8000_chars(self):
        """超过 8000 字符的结果被截断"""
        from routers.chat.tools.registry import execute_tool

        def big_result(**kwargs):
            return {"data": "x" * 10000}

        impls = {"big_tool": big_result}
        result_str = execute_tool(impls, "big_tool", {})
        assert len(result_str) <= 8100  # 8000 + "[truncated]" 的长度
        assert "truncated" in result_str

    def test_user_id_injected_for_declared_tool(self):
        """NEEDS_USER_ID 里的工具收到 _user_id 参数"""
        from routers.chat.tools.registry import NEEDS_USER_ID, execute_tool

        received = {}

        def capture_user(**kwargs):
            received.update(kwargs)
            return {"ok": True}

        tool_name = "test_needs_uid_tool"
        NEEDS_USER_ID.add(tool_name)
        impls = {tool_name: capture_user}

        try:
            execute_tool(impls, tool_name, {}, user_id="user-abc123")
            assert received.get("_user_id") == "user-abc123"
        finally:
            NEEDS_USER_ID.discard(tool_name)

    def test_user_id_not_injected_for_undeclared_tool(self):
        """没在 NEEDS_USER_ID 里的工具不收到 _user_id"""
        from routers.chat.tools.registry import execute_tool

        received = {}

        def capture(**kwargs):
            received.update(kwargs)
            return {"ok": True}

        impls = {"no_uid_tool": capture}
        execute_tool(impls, "no_uid_tool", {}, user_id="user-abc123")
        assert "_user_id" not in received

    def test_count_by_blocks_hidden_column_for_external(self):
        """count_by 拒绝外部用户对隐藏字段做聚合"""
        from routers.chat.tools.registry import execute_tool

        def fake_count_by(**kwargs):
            return [{"value": "高", "count": 5}]

        impls = {"count_by": fake_count_by}

        result = json.loads(
            execute_tool(
                impls,
                "count_by",
                {"table": "公司", "group_by": "BD跟进优先级"},
                can_see_internal=False,  # 外部用户
            )
        )
        assert "error" in result
        assert "不对外部用户开放" in result["error"]

    def test_count_by_allows_hidden_column_for_internal(self):
        """内部用户能对隐藏字段做聚合"""
        from routers.chat.tools.registry import execute_tool

        def fake_count_by(**kwargs):
            return [{"value": "高", "count": 5}]

        impls = {"count_by": fake_count_by}
        result = json.loads(
            execute_tool(
                impls,
                "count_by",
                {"table": "公司", "group_by": "BD跟进优先级"},
                can_see_internal=True,  # 内部用户
            )
        )
        # 不应该有 error，应该有正常结果
        assert "error" not in result or result.get("error") is None


# ════════════════════════════════════════════════════════════════
# 字段过滤在 execute_tool 中端到端生效
# ════════════════════════════════════════════════════════════════


class TestFieldFilteringEndToEnd:
    def test_search_companies_strips_internal_fields_for_external(self):
        """search_companies 的结果对外部用户自动剥离内部字段"""
        from routers.chat.tools.registry import TOOL_TABLE, execute_tool

        def fake_search(**kwargs):
            return [{"客户名称": "测试公司", "BD跟进优先级": "高", "内部备注": "机密"}]

        TOOL_TABLE["search_companies"] = "公司"
        impls = {"search_companies": fake_search}

        result = json.loads(execute_tool(impls, "search_companies", {}, can_see_internal=False))
        assert isinstance(result, list)
        assert "BD跟进优先级" not in result[0]
        assert "内部备注" not in result[0]
        assert result[0]["客户名称"] == "测试公司"

    def test_search_companies_keeps_all_fields_for_internal(self):
        """search_companies 对内部用户不剥离任何字段"""
        from routers.chat.tools.registry import TOOL_TABLE, execute_tool

        def fake_search(**kwargs):
            return [{"客户名称": "测试公司", "BD跟进优先级": "高", "内部备注": "机密"}]

        TOOL_TABLE["search_companies"] = "公司"
        impls = {"search_companies": fake_search}

        result = json.loads(execute_tool(impls, "search_companies", {}, can_see_internal=True))
        assert result[0]["BD跟进优先级"] == "高"
        assert result[0]["内部备注"] == "机密"
