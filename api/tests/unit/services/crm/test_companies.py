"""Unit tests for services/crm/companies — the pilot service module
extracted from routers/companies.py as part of S-002. Same pattern
will be applied to assets / clinical / deals / ip / buyers.
"""

from __future__ import annotations

from unittest.mock import patch


class TestFetchCompany:
    def test_returns_stripped_row_when_found(self):
        from services.crm import companies as svc

        raw_row = {"客户名称": "Pfizer", "BD跟进优先级": "A", "内部备注": "私有"}
        user = {"is_internal": False}

        with (
            patch("services.crm.companies.query_one") as mock_qone,
            patch("services.crm.companies.strip_hidden") as mock_strip,
        ):
            mock_qone.return_value = raw_row
            mock_strip.return_value = {"客户名称": "Pfizer"}
            result = svc.fetch_company("Pfizer", user)

        # SQL path — exactly one query, parameterised (no string-interp)
        assert mock_qone.call_args.args == (
            'SELECT * FROM "公司" WHERE "客户名称" = ?',
            ("Pfizer",),
        )
        mock_strip.assert_called_once_with(raw_row, "公司", user)
        assert result == {"客户名称": "Pfizer"}

    def test_returns_none_when_not_found(self):
        """strip_hidden must NOT run when the row doesn't exist —
        calling strip_hidden(None, ...) would 500."""
        from services.crm import companies as svc

        with (
            patch("services.crm.companies.query_one") as mock_qone,
            patch("services.crm.companies.strip_hidden") as mock_strip,
        ):
            mock_qone.return_value = None
            result = svc.fetch_company("Unknown", {"is_internal": False})

        assert result is None
        mock_strip.assert_not_called()


class TestFetchCompanyAssets:
    def test_paginates_by_所属客户_and_orders_by_stage(self):
        from services.crm import companies as svc

        user = {"is_internal": True}
        fake_page = {
            "data": [{"资产名称": "X"}],
            "page": 1,
            "page_size": 50,
            "total": 1,
            "total_pages": 1,
        }

        with (
            patch("services.crm.companies.paginate") as mock_paginate,
            patch("services.crm.companies.strip_hidden") as mock_strip,
        ):
            mock_paginate.return_value = dict(fake_page)
            mock_strip.return_value = fake_page["data"]
            svc.fetch_company_assets("Pfizer", page=1, page_size=50, user=user)

        kwargs = mock_paginate.call_args.kwargs
        assert mock_paginate.call_args.args[0] == "资产"
        assert kwargs["where"] == '"所属客户" = ?'
        assert kwargs["params"] == ("Pfizer",)
        assert kwargs["order_by"] == '"临床阶段" ASC'
        # strip_hidden gets the 资产 table key, not the company table.
        assert mock_strip.call_args.args == (fake_page["data"], "资产", user)


class TestFetchCompanyDeals:
    def test_matches_both_buyer_and_seller_positions(self):
        """A company's deals include any deal where it's the buyer OR
        the seller — both sides of the table need to be searched."""
        from services.crm import companies as svc

        user = {"is_internal": True}
        with (
            patch("services.crm.companies.query") as mock_q,
            patch("services.crm.companies.strip_hidden") as mock_strip,
        ):
            mock_q.return_value = [{"交易名称": "D1"}]
            mock_strip.return_value = [{"交易名称": "D1"}]
            svc.fetch_company_deals("Pfizer", user)

        sql, params = mock_q.call_args.args
        assert '"买方公司" = ?' in sql
        assert '"卖方/合作方" = ?' in sql
        assert params == ("Pfizer", "Pfizer")  # same name bound to both positions
        assert '"宣布日期" DESC' in sql
