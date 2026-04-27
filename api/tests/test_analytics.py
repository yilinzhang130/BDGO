"""Tests for analytics endpoints (P1-9).

Covers:
  1.  POST /api/analytics/event — returns 202 for any authenticated user
  2.  POST /api/analytics/event — background task is queued with correct args
  3.  POST /api/analytics/event — 401 without auth
  4.  GET  /api/analytics/outreach-funnel — 403 for non-admin
  5.  GET  /api/analytics/outreach-funnel — 200 with correct structure for admin
  6.  GET  /api/analytics/outreach-funnel — rate calculations are correct
  7.  GET  /api/analytics/outreach-funnel — window_days param is respected
  8.  GET  /api/analytics/slash-usage — 403 for non-admin
  9.  GET  /api/analytics/slash-usage — 200 with correct structure for admin
  10. GET  /api/analytics/slash-usage — days param is forwarded to SQL
  11. POST then GET — event queued, funnel returns (0-count) data
  12. _write_event — swallows DB errors silently
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helper — reuse the same pattern as test_team_router.py
# ---------------------------------------------------------------------------


def _mock_tx(rows_list=None, fetchone_val=None):
    """Return (patched_transaction, mock_cursor)."""
    mock_cur = MagicMock()
    if rows_list is not None:
        mock_cur.fetchall.return_value = rows_list
    if fetchone_val is not None:
        mock_cur.fetchone.return_value = fetchone_val
    mock_tx = MagicMock()
    mock_tx.return_value.__enter__ = lambda s: mock_cur
    mock_tx.return_value.__exit__ = MagicMock(return_value=False)
    return mock_tx, mock_cur


# ---------------------------------------------------------------------------
# 1-3. POST /api/analytics/event
# ---------------------------------------------------------------------------


def test_track_event_accepted(client, ext_headers):
    """Any authenticated user receives 202."""
    with patch("routers.analytics._write_event"):
        resp = client.post(
            "/api/analytics/event",
            headers=ext_headers,
            json={"event": "slash_used", "properties": {"slash": "/email"}},
        )
    assert resp.status_code == 202
    assert resp.json()["queued"] is True


def test_track_event_background_args(client, ext_headers, external_user):
    """Background task is called with the correct user_id, event, and properties."""
    with patch("routers.analytics._write_event") as mock_write:
        client.post(
            "/api/analytics/event",
            headers=ext_headers,
            json={"event": "slash_used", "properties": {"slash": "/outreach"}},
        )
    mock_write.assert_called_once_with(
        external_user["id"], "slash_used", {"slash": "/outreach"}
    )


def test_track_event_requires_auth(client):
    """Missing token → 401."""
    resp = client.post(
        "/api/analytics/event",
        json={"event": "test", "properties": {}},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4-7. GET /api/analytics/outreach-funnel
# ---------------------------------------------------------------------------


def test_outreach_funnel_non_admin_forbidden(client, ext_headers):
    """Non-admin user → 403."""
    resp = client.get("/api/analytics/outreach-funnel", headers=ext_headers)
    assert resp.status_code == 403


def test_outreach_funnel_returns_structure(client, admin_headers):
    """Admin gets a well-formed funnel response."""
    mock_tx, _ = _mock_tx(
        rows_list=[
            {"status": "sent", "cnt": 10},
            {"status": "replied", "cnt": 4},
            {"status": "cda_signed", "cnt": 1},
            {"status": "dead", "cnt": 2},
        ]
    )
    with patch("routers.analytics.transaction", mock_tx):
        resp = client.get("/api/analytics/outreach-funnel", headers=admin_headers)

    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "draft_count",
        "sent_count",
        "replied_count",
        "signed_count",
        "dropped_count",
        "draft_to_sent_rate",
        "sent_to_replied_rate",
        "replied_to_signed_rate",
        "window_days",
    }
    assert required_keys.issubset(data.keys())
    assert data["sent_count"] == 10
    assert data["replied_count"] == 4
    assert data["signed_count"] == 1
    assert data["dropped_count"] == 2
    assert data["window_days"] == 30


def test_outreach_funnel_rates(client, admin_headers):
    """Rate calculations: sent_to_replied = 4/10 = 0.4."""
    mock_tx, _ = _mock_tx(
        rows_list=[
            {"status": "sent", "cnt": 10},
            {"status": "replied", "cnt": 4},
        ]
    )
    with patch("routers.analytics.transaction", mock_tx):
        data = client.get("/api/analytics/outreach-funnel", headers=admin_headers).json()

    assert data["sent_to_replied_rate"] == 0.4


def test_outreach_funnel_zero_denominator(client, admin_headers):
    """No rows → all counts 0, rates 0.0 (no ZeroDivisionError)."""
    mock_tx, _ = _mock_tx(rows_list=[])
    with patch("routers.analytics.transaction", mock_tx):
        data = client.get("/api/analytics/outreach-funnel", headers=admin_headers).json()

    assert data["sent_count"] == 0
    assert data["sent_to_replied_rate"] == 0.0


def test_outreach_funnel_custom_days(client, admin_headers):
    """?days=7 is passed through to the response."""
    mock_tx, mock_cur = _mock_tx(rows_list=[])
    with patch("routers.analytics.transaction", mock_tx):
        data = client.get(
            "/api/analytics/outreach-funnel?days=7", headers=admin_headers
        ).json()

    assert data["window_days"] == 7
    sql_call = mock_cur.execute.call_args
    assert "7" in str(sql_call)


# ---------------------------------------------------------------------------
# 8-10. GET /api/analytics/slash-usage
# ---------------------------------------------------------------------------


def test_slash_usage_non_admin_forbidden(client, ext_headers):
    """Non-admin → 403."""
    resp = client.get("/api/analytics/slash-usage", headers=ext_headers)
    assert resp.status_code == 403


def test_slash_usage_returns_data(client, admin_headers):
    """Admin gets slug list sorted by count."""
    mock_tx, _ = _mock_tx(
        rows_list=[
            {"slug": "email", "cnt": 42},
            {"slug": "outreach", "cnt": 17},
        ]
    )
    with patch("routers.analytics.transaction", mock_tx):
        resp = client.get("/api/analytics/slash-usage", headers=admin_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["window_days"] == 30
    assert data["data"][0] == {"slug": "email", "count": 42}
    assert data["data"][1] == {"slug": "outreach", "count": 17}


def test_slash_usage_custom_days_forwarded(client, admin_headers):
    """?days=14 flows through to SQL and response."""
    mock_tx, mock_cur = _mock_tx(rows_list=[])
    with patch("routers.analytics.transaction", mock_tx):
        data = client.get("/api/analytics/slash-usage?days=14", headers=admin_headers).json()

    assert data["window_days"] == 14
    assert "14" in str(mock_cur.execute.call_args)


# ---------------------------------------------------------------------------
# 11. POST then GET — integration smoke
# ---------------------------------------------------------------------------


def test_post_then_get_funnel(client, admin_headers):
    """POST event succeeds; subsequent GET funnel returns a valid (zero) response."""
    with patch("routers.analytics._write_event") as mock_write:
        post_resp = client.post(
            "/api/analytics/event",
            headers=admin_headers,
            json={"event": "baseline_snapshot", "properties": {"source": "test"}},
        )
    assert post_resp.status_code == 202
    mock_write.assert_called_once()

    mock_tx, _ = _mock_tx(rows_list=[])
    with patch("routers.analytics.transaction", mock_tx):
        get_resp = client.get("/api/analytics/outreach-funnel", headers=admin_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["sent_count"] == 0


# ---------------------------------------------------------------------------
# 12. _write_event error resilience
# ---------------------------------------------------------------------------


def test_write_event_swallows_db_error():
    """_write_event never raises even when the DB blows up."""
    from routers.analytics import _write_event

    broken_tx = MagicMock()
    broken_tx.return_value.__enter__ = MagicMock(side_effect=RuntimeError("DB down"))
    broken_tx.return_value.__exit__ = MagicMock(return_value=False)

    with patch("routers.analytics.transaction", broken_tx):
        _write_event("user-123", "test_event", {})  # must not raise
