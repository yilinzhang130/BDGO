"""Unit tests for services/crm/list_view.list_table_view — the 3-step
sort-validate → paginate → strip_hidden pipeline the 6 CRUD routers
share (see S-004)."""

from __future__ import annotations

from unittest.mock import patch


def _mock_paginate_return(data=None):
    return {
        "data": data if data is not None else [{"客户名称": "A"}, {"客户名称": "B"}],
        "page": 1,
        "page_size": 50,
        "total": 2,
        "total_pages": 1,
    }


class TestSortAllowlist:
    """The allowlist is a per-table business rule — an unknown sort
    must fall back to the default, not pass through as SQL ORDER BY
    (that would be a bypass)."""

    def test_unknown_sort_falls_back_to_default(self):
        from services.crm.list_view import list_table_view

        with patch("services.crm.list_view.paginate") as mock_paginate:
            mock_paginate.return_value = _mock_paginate_return()
            list_table_view(
                "公司",
                where="",
                params=(),
                sort="DROP TABLE",  # not in allowlist
                order="asc",
                sort_allowlist={"客户名称", "所处国家"},
                default_sort="客户名称",
                page=1,
                page_size=50,
                user=None,
            )
        # The order_by must reference the default, not the hostile value.
        order_by = mock_paginate.call_args.kwargs["order_by"]
        assert "客户名称" in order_by
        assert "DROP TABLE" not in order_by

    def test_allowlisted_sort_passes_through(self):
        from services.crm.list_view import list_table_view

        with patch("services.crm.list_view.paginate") as mock_paginate:
            mock_paginate.return_value = _mock_paginate_return()
            list_table_view(
                "公司",
                where="",
                params=(),
                sort="所处国家",
                order="asc",
                sort_allowlist={"客户名称", "所处国家"},
                default_sort="客户名称",
                page=1,
                page_size=50,
                user=None,
            )
        assert '"所处国家"' in mock_paginate.call_args.kwargs["order_by"]


class TestOrderDirection:
    def test_desc_applied(self):
        from services.crm.list_view import list_table_view

        with patch("services.crm.list_view.paginate") as mock_paginate:
            mock_paginate.return_value = _mock_paginate_return()
            list_table_view(
                "公司",
                where="",
                params=(),
                sort="客户名称",
                order="desc",
                sort_allowlist={"客户名称"},
                default_sort="客户名称",
                page=1,
                page_size=50,
                user=None,
            )
        assert " DESC" in mock_paginate.call_args.kwargs["order_by"]

    def test_unknown_order_defaults_to_asc(self):
        """Any non-'desc' value (including garbage) becomes ASC."""
        from services.crm.list_view import list_table_view

        with patch("services.crm.list_view.paginate") as mock_paginate:
            mock_paginate.return_value = _mock_paginate_return()
            list_table_view(
                "公司",
                where="",
                params=(),
                sort="客户名称",
                order="sideways",
                sort_allowlist={"客户名称"},
                default_sort="客户名称",
                page=1,
                page_size=50,
                user=None,
            )
        assert " ASC" in mock_paginate.call_args.kwargs["order_by"]


class TestStripHidden:
    def test_user_none_skips_strip(self):
        """Tables without per-user visibility (MNC画像 / IP) pass
        user=None — strip_hidden must not run."""
        from services.crm.list_view import list_table_view

        with (
            patch("services.crm.list_view.paginate") as mock_paginate,
            patch("services.crm.list_view.strip_hidden") as mock_strip,
        ):
            mock_paginate.return_value = _mock_paginate_return()
            list_table_view(
                "MNC画像",
                where="",
                params=(),
                sort="company_name",
                order="asc",
                sort_allowlist={"company_name"},
                default_sort="company_name",
                page=1,
                page_size=50,
                user=None,
            )
        mock_strip.assert_not_called()

    def test_user_present_calls_strip_with_right_args(self):
        from services.crm.list_view import list_table_view

        rows = [{"客户名称": "A", "内部备注": "private"}]
        user = {"is_internal": False}

        with (
            patch("services.crm.list_view.paginate") as mock_paginate,
            patch("services.crm.list_view.strip_hidden") as mock_strip,
        ):
            mock_paginate.return_value = _mock_paginate_return(rows)
            mock_strip.return_value = [{"客户名称": "A"}]
            result = list_table_view(
                "公司",
                where="",
                params=(),
                sort="客户名称",
                order="asc",
                sort_allowlist={"客户名称"},
                default_sort="客户名称",
                page=1,
                page_size=50,
                user=user,
            )
        mock_strip.assert_called_once_with(rows, "公司", user)
        assert result["data"] == [{"客户名称": "A"}]


class TestPaginatedResponseSchema:
    """PaginatedResponse is what FastAPI validates responses against
    for every list endpoint. Missing fields silently 500."""

    def test_accepts_canonical_payload(self):
        from services.crm.list_view import PaginatedResponse

        resp = PaginatedResponse(
            data=[{"x": 1}],
            page=1,
            page_size=50,
            total=1,
            total_pages=1,
        )
        assert resp.total == 1

    def test_rejects_missing_total_pages(self):
        import pytest
        from pydantic import ValidationError
        from services.crm.list_view import PaginatedResponse

        with pytest.raises(ValidationError):
            PaginatedResponse(data=[], page=1, page_size=50, total=0)  # no total_pages
