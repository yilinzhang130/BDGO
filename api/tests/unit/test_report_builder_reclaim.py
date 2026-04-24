"""
Unit tests for ``report_builder.reclaim_stale_tasks``.

We don't touch Postgres here — the function delegates the whole SQL
dance to ``auth_db.transaction``; mocking that lets us verify the
contract (what SQL, what params, what the caller does with rowcount)
without a live DB.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _mock_transaction(rowcount: int):
    """Build a MagicMock that mimics auth_db.transaction's context manager
    and returns a cursor whose .rowcount matches what we want."""
    mock_cur = MagicMock()
    mock_cur.rowcount = rowcount
    mock_tx = MagicMock()
    mock_tx.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_tx.return_value.__exit__ = MagicMock(return_value=False)
    return mock_tx, mock_cur


class TestReclaimStaleTasks:
    def test_returns_rowcount_when_orphans_reclaimed(self):
        from services.report_builder import reclaim_stale_tasks

        mock_tx, _ = _mock_transaction(rowcount=3)
        with patch("auth_db.transaction", mock_tx):
            n = reclaim_stale_tasks(max_age_seconds=900)

        assert n == 3

    def test_returns_zero_when_nothing_stale(self):
        from services.report_builder import reclaim_stale_tasks

        mock_tx, _ = _mock_transaction(rowcount=0)
        with patch("auth_db.transaction", mock_tx):
            n = reclaim_stale_tasks(max_age_seconds=900)

        assert n == 0

    def test_only_targets_queued_and_running(self):
        """The UPDATE must only flip rows whose status is queued or
        running. Completed/failed rows are final — touching them would
        rewrite history."""
        from services.report_builder import STATUS_QUEUED, STATUS_RUNNING, reclaim_stale_tasks

        mock_tx, mock_cur = _mock_transaction(rowcount=1)
        with patch("auth_db.transaction", mock_tx):
            reclaim_stale_tasks(max_age_seconds=600)

        # One execute call; params include the two statuses we target.
        assert mock_cur.execute.called
        _sql, params = mock_cur.execute.call_args[0]
        assert STATUS_QUEUED in params
        assert STATUS_RUNNING in params

    def test_swallow_db_errors_returns_zero(self):
        """DB connectivity blips shouldn't crash startup."""
        from services.report_builder import reclaim_stale_tasks

        def _boom(*args, **kwargs):
            raise RuntimeError("pg down")

        with patch("auth_db.transaction", side_effect=_boom):
            n = reclaim_stale_tasks(max_age_seconds=900)

        assert n == 0

    def test_uses_coalesce_started_created(self):
        """SQL must fall back to created_at when started_at is null —
        a task that died before _update_state(RUNNING) still needs to
        be reclaimed."""
        from services.report_builder import reclaim_stale_tasks

        mock_tx, mock_cur = _mock_transaction(rowcount=0)
        with patch("auth_db.transaction", mock_tx):
            reclaim_stale_tasks(max_age_seconds=900)

        sql, _ = mock_cur.execute.call_args[0]
        assert "COALESCE" in sql.upper()
        assert "started_at" in sql
        assert "created_at" in sql
