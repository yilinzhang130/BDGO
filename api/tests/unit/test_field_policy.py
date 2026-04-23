"""
单元测试：field_policy.py

测什么：
    - 外部用户看不到隐藏字段（数据泄露防护）
    - 内部用户/管理员能看到所有字段
    - strip_hidden 能处理单行 dict 和多行 list
    - 空数据不崩溃

为什么这些测试最重要：
    如果 strip_hidden 有 bug，内部 BD 评分、优先级等敏感信息
    就会通过 API 泄露给外部合作伙伴。
"""

from field_policy import HIDDEN_FIELDS, can_see_internal_fields, strip_hidden

# ════════════════════════════════════════════════════════════════
# can_see_internal_fields
# ════════════════��═════════════════════���═════════════════════════


class TestCanSeeInternalFields:
    def test_external_user_cannot_see(self, external_user):
        assert can_see_internal_fields(external_user) is False

    def test_internal_user_can_see(self, internal_user):
        assert can_see_internal_fields(internal_user) is True

    def test_admin_user_can_see(self, admin_user):
        assert can_see_internal_fields(admin_user) is True

    def test_none_cannot_see(self):
        assert can_see_internal_fields(None) is False

    def test_empty_dict_cannot_see(self):
        assert can_see_internal_fields({}) is False

    def test_only_is_admin_true_can_see(self):
        # 只有 is_admin=True，没有 is_internal
        user = {"is_admin": True, "is_internal": False}
        assert can_see_internal_fields(user) is True

    def test_only_is_internal_true_can_see(self):
        user = {"is_admin": False, "is_internal": True}
        assert can_see_internal_fields(user) is True


# ═══════════════════════════════════════��════════════════════════
# strip_hidden — 字段剥离核心逻辑
# ═════════════════════════════════════════════════════════���══════


class TestStripHidden:
    # ── 单行 dict ──────────────────────────────────────────────

    def test_external_cannot_see_bd_priority(self, sample_company_row, external_user):
        """外部用户不能看到 BD跟进优先级"""
        result = strip_hidden(sample_company_row, "公司", external_user)
        assert "BD跟进优先级" not in result

    def test_external_cannot_see_internal_score(self, sample_company_row, external_user):
        """外部用户不能看到 公司质量评分"""
        result = strip_hidden(sample_company_row, "公司", external_user)
        assert "公司质量评分" not in result

    def test_external_cannot_see_internal_notes(self, sample_company_row, external_user):
        """外部用户不能看到 内部备注"""
        result = strip_hidden(sample_company_row, "公司", external_user)
        assert "内部备注" not in result

    def test_external_can_see_public_fields(self, sample_company_row, external_user):
        """外部用户能看到公开字段"""
        result = strip_hidden(sample_company_row, "公司", external_user)
        assert result["客户名称"] == "测试生物科技"
        assert result["客户类型"] == "Biotech"
        assert result["疾病领域"] == "Oncology"

    def test_internal_sees_all_fields(self, sample_company_row, internal_user):
        """内部用户看到所有字段，包括隐藏字段"""
        result = strip_hidden(sample_company_row, "公司", internal_user)
        assert result["BD跟进优先级"] == "高"
        assert result["公司质量评分"] == 85
        assert result["内部备注"] == "重点跟进"

    def test_admin_sees_all_fields(self, sample_company_row, admin_user):
        """管理员看到所有字段"""
        result = strip_hidden(sample_company_row, "公司", admin_user)
        assert "BD跟进优先级" in result
        assert "公司质量评分" in result

    # ── 资产表 ────────────────────────────────────────────────

    def test_external_cannot_see_q_scores(self, sample_asset_row, external_user):
        """外部用户看不到 Q1-Q4 评分"""
        result = strip_hidden(sample_asset_row, "资产", external_user)
        for q_field in ["Q总分", "Q1_生物学", "Q2_药物形式", "Q3_临床监管", "Q4_商业交易性"]:
            assert q_field not in result, f"字段 {q_field} 不应该对外部用户可见"

    def test_external_can_see_asset_basics(self, sample_asset_row, external_user):
        """外部用户能看到资产基本信息"""
        result = strip_hidden(sample_asset_row, "资产", external_user)
        assert result["资产名称"] == "TestDrug-001"
        assert result["临床阶段"] == "Phase 2"
        assert result["靶点"] == "EGFR"

    # ── 多行 list ─────────────────────────────────────────────

    def test_strips_list_of_rows(self, external_user):
        """能批量处理多行数据"""
        rows = [
            {"客户名称": "公司A", "BD跟进优先级": "高", "内部备注": "机密"},
            {"客户名称": "公司B", "BD跟进优先级": "中", "内部备注": "机密"},
        ]
        result = strip_hidden(rows, "公司", external_user)
        assert isinstance(result, list)
        assert len(result) == 2
        for row in result:
            assert "BD跟进优先级" not in row
            assert "内部备注" not in row
            assert "客户名称" in row

    def test_strips_empty_list(self, external_user):
        """空列表不崩溃"""
        result = strip_hidden([], "公司", external_user)
        assert result == []

    def test_strips_none_value_field(self, external_user):
        """字段值为 None 时正常处理"""
        row = {"客户名称": "公司A", "BD跟进优先级": None}
        result = strip_hidden(row, "公司", external_user)
        assert "BD跟进优先级" not in result
        assert result["客户名称"] == "公司A"

    # ── 布尔值 legacy 路径 ───────────────────���────────────────

    def test_bool_true_shows_all(self, sample_company_row):
        """strip_hidden(row, table, True) 显示全部（向后兼容）"""
        result = strip_hidden(sample_company_row, "公司", True)
        assert "BD跟进优先级" in result

    def test_bool_false_strips(self, sample_company_row):
        """strip_hidden(row, table, False) 执行剥离"""
        result = strip_hidden(sample_company_row, "公司", False)
        assert "BD跟进优先级" not in result

    # ── 未知表名 ───────────────────────���──────────────────────

    def test_unknown_table_returns_row_unchanged(self, external_user):
        """不在 HIDDEN_FIELDS 里的表名，不剥离任何字段"""
        row = {"字段A": "值A", "字段B": "值B"}
        result = strip_hidden(row, "不存在的表", external_user)
        assert result == row

    # ── 确保 HIDDEN_FIELDS 覆盖所有关键表 ────────────────────

    def test_hidden_fields_covers_main_tables(self):
        """确认四张主表都有字段保护规则"""
        for table in ["公司", "资产", "交易", "临床"]:
            assert table in HIDDEN_FIELDS, f"表 '{table}' 缺少字段保护规则"
            assert len(HIDDEN_FIELDS[table]) > 0, f"表 '{table}' 的隐藏字段列表为空"
