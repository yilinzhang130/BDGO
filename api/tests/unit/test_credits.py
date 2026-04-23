"""
单元测试：credits.py 里的积分计算逻辑

测什么：
    - credits_charged 公式正确
    - 0 token 情况不产生负数
    - 极大 token 数不溢出
    - ensure_balance 在余额不足时正确抛出 402

注意：这里只测"纯计算"部分，不测 DB 操作。
DB 相关的测试需要真实 Postgres，放到 integration/ 里。
"""

from unittest.mock import MagicMock, patch

import pytest


class TestCreditFormula:
    """
    测试 credits.calc_credits 公式（record_usage 的纯计算部分）：
        credits = input_tokens * input_weight + output_tokens * output_weight

    直接调真函数而不是 re-implement —— 这样公式改了测试会立刻跟着动。
    """

    def test_basic_calculation(self):
        from credits import calc_credits

        assert calc_credits(1000, 500, 0.001, 0.003) == 2.5  # 1000*0.001 + 500*0.003

    def test_zero_tokens_zero_charge(self):
        from credits import calc_credits

        assert calc_credits(0, 0, 0.001, 0.003) == 0.0

    def test_only_input_tokens(self):
        from credits import calc_credits

        assert calc_credits(2000, 0, 0.001, 0.003) == 2.0

    def test_only_output_tokens(self):
        from credits import calc_credits

        assert calc_credits(0, 1000, 0.001, 0.005) == 5.0

    def test_negative_tokens_treated_as_zero(self):
        """负数 token 不应产生负积分"""
        from credits import calc_credits

        assert calc_credits(-100, -200, 0.001, 0.003) == 0.0

    def test_large_token_count(self):
        """80k context window 不溢出"""
        from credits import calc_credits

        result = calc_credits(80_000, 8_000, 0.001, 0.003)
        assert result == 80 + 24  # == 104.0
        assert result > 0

    def test_rounding_to_2_decimal_places(self):
        """结果精确到 2 位小数"""
        from credits import calc_credits

        assert calc_credits(1, 1, 0.0015, 0.0025) == 0.0  # round(0.004, 2) == 0.0
        assert calc_credits(100, 100, 0.0015, 0.0025) == 0.4  # 0.15 + 0.25


class TestEnsureBalance:
    """
    测试 ensure_balance — 余额不足时抛出 HTTP 402
    """

    def test_raises_402_when_balance_zero(self):
        """余额为 0 时抛出 402"""
        from credits import ensure_balance
        from fastapi import HTTPException

        # mock auth_db.transaction 让它返回一个假余额
        mock_row = {"balance": "0.00"}
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = mock_row

        with patch("credits.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(HTTPException) as exc_info:
                ensure_balance("user-broke")

        assert exc_info.value.status_code == 402
        assert "余额不足" in exc_info.value.detail

    def test_raises_402_when_balance_below_minimum(self):
        """余额低于最小要求时抛出 402"""
        from credits import ensure_balance
        from fastapi import HTTPException

        mock_row = {"balance": "5.00"}  # 低于默认最小值 10
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = mock_row

        with patch("credits.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(HTTPException) as exc_info:
                ensure_balance("user-low", min_credits=10)

        assert exc_info.value.status_code == 402

    def test_passes_when_balance_sufficient(self):
        """余额充足时不抛异常"""
        from credits import ensure_balance

        mock_row = {"balance": "10000.00"}
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = mock_row

        with patch("credits.auth_db.transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            # 不应该抛异常
            ensure_balance("user-rich")
