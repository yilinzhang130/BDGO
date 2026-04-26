"""Unit tests for the team features router (P3-14).

Tests cover:
  1.  GET /api/team/members returns a list
  2.  Members list excludes the requesting user
  3.  GET /api/team/notifications returns unread count + items
  4.  GET /api/team/notifications/unread-count
  5.  PATCH /api/team/notifications/{id}/read marks one read
  6.  PATCH /api/team/notifications/read-all marks all read
  7.  send_notification() inserts a row (mocked)
  8.  send_notification() is silent on DB error (no raise)
  9.  POST /api/watchlist/{id}/share — 404 on unknown item
 10.  POST /api/watchlist/{id}/share — 400 on bad permission
 11.  POST /api/watchlist/{id}/share — success path (mocked)
 12.  GET /api/watchlist/shared returns list
 13.  DELETE /api/watchlist/{id}/share/{uid} — 404 on missing share
 14.  POST /api/reports/notify — 404 on unknown report
 15.  POST /api/reports/notify — success path (mocked)
 16.  DB tables: user_notifications and watchlist_shares in schema SQL
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────
# 1-2. /api/team/members
# ─────────────────────────────────────────────────────────────


def _mock_tx(rows_list=None, fetchone_list=None):
    """Build a patched transaction() context manager."""
    mock_cur = MagicMock()
    if rows_list is not None:
        mock_cur.fetchall.return_value = rows_list
    if fetchone_list is not None:
        mock_cur.fetchone.side_effect = fetchone_list
    mock_tx = MagicMock()
    mock_tx.return_value.__enter__ = lambda s: mock_cur
    mock_tx.return_value.__exit__ = MagicMock(return_value=False)
    return mock_tx, mock_cur


def test_members_returns_list(client, ext_headers):
    fake_rows = [
        {"id": "uuid-2", "name": "Alice", "email": "alice@corp.com", "avatar_url": None, "title": None}
    ]
    mock_tx, _ = _mock_tx(rows_list=fake_rows)
    with patch("routers.team.transaction", mock_tx):
        resp = client.get("/api/team/members", headers=ext_headers)

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_members_excludes_self(client, ext_headers):
    """Verify SQL exclusion of caller's user id."""
    mock_tx, mock_cur = _mock_tx(rows_list=[])
    with patch("routers.team.transaction", mock_tx):
        resp = client.get("/api/team/members", headers=ext_headers)

    assert resp.status_code == 200
    calls = mock_cur.execute.call_args_list
    assert any("id != %s" in str(c) for c in calls)


# ─────────────────────────────────────────────────────────────
# 3-6. Notification endpoints
# ─────────────────────────────────────────────────────────────


def test_list_notifications(client, ext_headers):
    rows = [
        {
            "id": 1, "type": "report_share", "title": "Bob shared a report",
            "body": "Pfizer analysis", "link_url": "/share/abc",
            "read_at": None, "created_at": "2026-04-26T10:00:00",
            "sender_name": "Bob", "sender_avatar": None,
        }
    ]
    mock_tx, mock_cur = _mock_tx(
        rows_list=rows,
        fetchone_list=[{"cnt": 1}, {"cnt": 1}],
    )
    with patch("routers.team.transaction", mock_tx):
        resp = client.get("/api/team/notifications", headers=ext_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["unread"] == 1
    assert data["items"][0]["title"] == "Bob shared a report"


def test_unread_count(client, ext_headers):
    mock_tx, mock_cur = _mock_tx(fetchone_list=[{"cnt": 3}])
    with patch("routers.team.transaction", mock_tx):
        resp = client.get("/api/team/notifications/unread-count", headers=ext_headers)

    assert resp.status_code == 200
    assert resp.json()["count"] == 3


def test_mark_notification_read(client, ext_headers):
    with patch("routers.team.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.patch("/api/team/notifications/42/read", headers=ext_headers)

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_cur.execute.assert_called_once()
    sql = mock_cur.execute.call_args[0][0]
    assert "42" in str(mock_cur.execute.call_args[0][1]) or "%s" in sql


def test_mark_all_notifications_read(client, ext_headers):
    with patch("routers.team.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.patch("/api/team/notifications/read-all", headers=ext_headers)

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ─────────────────────────────────────────────────────────────
# 7-8. send_notification helper
# ─────────────────────────────────────────────────────────────


def test_send_notification_inserts_row():
    from routers.team import send_notification

    with patch("routers.team.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        send_notification("recv-id", "send-id", "report_share", "Test title", "Body", "/link")

    mock_cur.execute.assert_called_once()
    args = mock_cur.execute.call_args[0][1]
    assert args[0] == "recv-id"
    assert args[2] == "report_share"
    assert args[3] == "Test title"


def test_send_notification_silent_on_error():
    from routers.team import send_notification

    with patch("routers.team.transaction", side_effect=RuntimeError("db down")):
        # Must not raise
        send_notification("r", "s", "mention", "Hi")


# ─────────────────────────────────────────────────────────────
# 9-13. Watchlist share endpoints
# ─────────────────────────────────────────────────────────────


def test_share_watchlist_404_on_unknown_item(client, ext_headers):
    with patch("routers.watchlist.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None  # item not found
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.post(
            "/api/watchlist/999/share",
            headers=ext_headers,
            json={"user_id": "uid-2", "permission": "view"},
        )
    assert resp.status_code == 404


def test_share_watchlist_400_bad_permission(client, ext_headers):
    with patch("routers.watchlist.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.post(
            "/api/watchlist/1/share",
            headers=ext_headers,
            json={"user_id": "uid-2", "permission": "superuser"},
        )
    assert resp.status_code == 400


def test_share_watchlist_success(client, ext_headers):
    item_row = {"id": 1, "entity_type": "company", "entity_key": "Pfizer"}
    recipient_row = {"id": "uid-2", "name": "Alice"}
    share_row = {"id": 77}

    with (
        patch("routers.watchlist.transaction") as mock_tx,
        patch("routers.watchlist.send_notification") as mock_notify,
    ):
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [item_row, recipient_row, share_row]
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.post(
            "/api/watchlist/1/share",
            headers=ext_headers,
            json={"user_id": "uid-2", "permission": "view", "note": "check this"},
        )

    assert resp.status_code == 200
    assert resp.json()["share_id"] == 77
    mock_notify.assert_called_once()


def test_get_shared_with_me(client, ext_headers):
    rows = [
        {
            "share_id": 1, "item_id": 10, "entity_type": "company",
            "entity_key": "Roche", "notes": None, "owner_id": "uid-3",
            "owner_name": "Carol", "owner_email": "carol@corp.com",
            "permission": "view", "shared_at": "2026-04-26T09:00:00",
        }
    ]
    mock_tx, _ = _mock_tx(rows_list=rows)
    with patch("routers.watchlist.transaction", mock_tx):
        resp = client.get("/api/watchlist/shared", headers=ext_headers)

    assert resp.status_code == 200
    assert resp.json()[0]["entity_key"] == "Roche"


def test_delete_share_404(client, ext_headers):
    with patch("routers.watchlist.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.delete("/api/watchlist/1/share/uid-2", headers=ext_headers)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────
# 14-15. Report notify endpoint
# ─────────────────────────────────────────────────────────────


def test_notify_teammate_404_unknown_report(client, ext_headers):
    with patch("routers.reports.transaction") as mock_tx:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None  # report not found
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.post(
            "/api/reports/notify",
            headers=ext_headers,
            json={"task_id": "nonexistent", "recipient_id": "uid-2"},
        )
    assert resp.status_code == 404


def test_notify_teammate_success(client, ext_headers):
    report_row = {"title": "Pfizer Analysis"}
    recipient_row = {"id": "uid-2", "name": "Alice"}
    share_row = {"token": "existing_token"}

    with (
        patch("routers.reports.transaction") as mock_tx,
        patch("routers.reports.send_notification") as mock_notify,
    ):
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [report_row, recipient_row, share_row]
        mock_tx.return_value.__enter__ = lambda s: mock_cur
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.post(
            "/api/reports/notify",
            headers=ext_headers,
            json={"task_id": "task-abc", "recipient_id": "uid-2", "note": "see this"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == "existing_token"
    assert data["ok"] is True
    mock_notify.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 16. Schema SQL contains new tables
# ─────────────────────────────────────────────────────────────


def test_schema_has_user_notifications_table():
    import auth_db

    assert "user_notifications" in auth_db._SCHEMA_SQL


def test_schema_has_watchlist_shares_table():
    import auth_db

    assert "watchlist_shares" in auth_db._SCHEMA_SQL
