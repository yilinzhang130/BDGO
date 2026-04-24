"""
Integration tests for /api/sessions CRUD against a real Postgres.

Exercises the wiring that unit tests mock out:
  - auth_db schema for sessions / messages / context_entities
  - ON DELETE CASCADE from sessions → messages / entities
  - _verify_owner cross-user isolation at the SQL layer
  - sessions.updated_at bump on message insert
  - context_entities ON CONFLICT upsert

These assertions are DB-visible behaviors (cascades, timestamps, row
ownership) that a mocked cursor can silently let through. See
test_auth_flow.py for the fixture pattern this mirrors.
"""

from __future__ import annotations

import uuid


def _fresh_email() -> str:
    return f"it-sess-{uuid.uuid4().hex[:8]}@integration.test"


def _fresh_invite_code(cur) -> str:
    code = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    cur.execute(
        "INSERT INTO invite_codes (code, note, max_uses) VALUES (%s, %s, %s)",
        (code, "sessions-integration", 1),
    )
    return code


def _register_user(client, email: str) -> tuple[str, str]:
    """Register a fresh user; return (user_id, bearer_token).

    Caller owns the cleanup (DELETE FROM users WHERE email = ...).
    """
    from auth_db import transaction

    with transaction() as cur:
        code = _fresh_invite_code(cur)

    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "name": "Sess Tester",
            "invite_code": code,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["user"]["id"], body["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _cleanup(email: str) -> None:
    from auth_db import transaction

    with transaction() as cur:
        cur.execute("DELETE FROM users WHERE email = %s", (email,))


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


def test_session_crud_round_trip(integration_client):
    """create → list → get → rename → delete should round-trip cleanly."""
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        # create
        r = integration_client.post("/api/sessions", json={"title": "First"}, headers=_auth(token))
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        assert r.json()["title"] == "First"

        # list — new session should be present
        r = integration_client.get("/api/sessions", headers=_auth(token))
        assert r.status_code == 200, r.text
        ids = [s["id"] for s in r.json()]
        assert sid in ids

        # get
        r = integration_client.get(f"/api/sessions/{sid}", headers=_auth(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == sid
        assert body["messages"] == []
        assert body["context_entities"] == []

        # rename
        r = integration_client.put(
            f"/api/sessions/{sid}", json={"title": "Renamed"}, headers=_auth(token)
        )
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Renamed"

        # delete
        r = integration_client.delete(f"/api/sessions/{sid}", headers=_auth(token))
        assert r.status_code == 200, r.text

        # subsequent get → 404
        r = integration_client.get(f"/api/sessions/{sid}", headers=_auth(token))
        assert r.status_code == 404, r.text
    finally:
        _cleanup(email)


def test_message_post_bumps_session_updated_at(integration_client):
    """POST /sessions/{id}/messages must bump sessions.updated_at.

    Without this, sessions sort-by-updated_at would not reflect activity.
    """
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post("/api/sessions", json={"title": "T"}, headers=_auth(token))
        sid = r.json()["id"]
        initial_updated_at = r.json()["updated_at"]

        r = integration_client.post(
            f"/api/sessions/{sid}/messages",
            json={"role": "user", "content": "hi"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg["role"] == "user"
        assert msg["content"] == "hi"

        r = integration_client.get(f"/api/sessions/{sid}", headers=_auth(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["updated_at"] > initial_updated_at
        assert len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "hi"
    finally:
        _cleanup(email)


def test_session_delete_cascades_to_messages_and_entities(integration_client):
    """DELETE sessions must cascade to messages + context_entities.

    The schema declares ON DELETE CASCADE; this test protects the
    constraint from being silently dropped in a future migration.
    """
    from auth_db import transaction

    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post("/api/sessions", json={"title": "X"}, headers=_auth(token))
        sid = r.json()["id"]

        # Add a message + entity
        integration_client.post(
            f"/api/sessions/{sid}/messages",
            json={"role": "user", "content": "seed"},
            headers=_auth(token),
        )
        integration_client.post(
            f"/api/sessions/{sid}/entities",
            json={"id": "company:acme", "entity_type": "company", "title": "Acme"},
            headers=_auth(token),
        )

        # Sanity: both rows exist
        with transaction() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM messages WHERE session_id = %s", (sid,))
            assert cur.fetchone()["c"] == 1
            cur.execute("SELECT COUNT(*) AS c FROM context_entities WHERE session_id = %s", (sid,))
            assert cur.fetchone()["c"] == 1

        # Delete the session
        r = integration_client.delete(f"/api/sessions/{sid}", headers=_auth(token))
        assert r.status_code == 200, r.text

        # Cascade verified at the DB layer
        with transaction() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM messages WHERE session_id = %s", (sid,))
            assert cur.fetchone()["c"] == 0
            cur.execute("SELECT COUNT(*) AS c FROM context_entities WHERE session_id = %s", (sid,))
            assert cur.fetchone()["c"] == 0
    finally:
        _cleanup(email)


# ---------------------------------------------------------------------------
# Context entity upsert
# ---------------------------------------------------------------------------


def test_entity_upsert_replaces_on_conflict(integration_client):
    """POST /entities with a repeat id must UPDATE, not create a duplicate.

    The ON CONFLICT (id) DO UPDATE clause is how the frontend re-adds
    an already-pinned entity with fresher fields.
    """
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post("/api/sessions", json={"title": "E"}, headers=_auth(token))
        sid = r.json()["id"]

        first = integration_client.post(
            f"/api/sessions/{sid}/entities",
            json={
                "id": "asset:foo",
                "entity_type": "asset",
                "title": "Foo",
                "subtitle": "v1",
            },
            headers=_auth(token),
        )
        assert first.status_code == 200, first.text
        assert first.json()["subtitle"] == "v1"

        second = integration_client.post(
            f"/api/sessions/{sid}/entities",
            json={
                "id": "asset:foo",
                "entity_type": "asset",
                "title": "Foo",
                "subtitle": "v2",
            },
            headers=_auth(token),
        )
        assert second.status_code == 200, second.text
        assert second.json()["subtitle"] == "v2"

        # Still exactly one row
        detail = integration_client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
        assert len(detail["context_entities"]) == 1
        assert detail["context_entities"][0]["subtitle"] == "v2"
    finally:
        _cleanup(email)


def test_entity_delete_404_when_missing(integration_client):
    """DELETE an entity that was never created must 404, not 200.

    Preserves the invariant the frontend relies on to detect stale
    context-panel state.
    """
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post("/api/sessions", json={"title": "D"}, headers=_auth(token))
        sid = r.json()["id"]

        r = integration_client.delete(
            f"/api/sessions/{sid}/entities/does-not-exist", headers=_auth(token)
        )
        assert r.status_code == 404, r.text
    finally:
        _cleanup(email)


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


def test_user_cannot_access_another_users_session(integration_client):
    """User A's token must get 404 on every session endpoint for B's session.

    _verify_owner returns the same 404 as 'not found' to avoid leaking
    existence of another user's rows. This test guards that behavior.
    """
    email_a = _fresh_email()
    email_b = _fresh_email()
    _, token_a = _register_user(integration_client, email_a)
    _, token_b = _register_user(integration_client, email_b)
    try:
        # B creates a session
        r = integration_client.post("/api/sessions", json={"title": "B's"}, headers=_auth(token_b))
        b_sid = r.json()["id"]

        # A must not be able to read / rename / delete / post-to it.
        r = integration_client.get(f"/api/sessions/{b_sid}", headers=_auth(token_a))
        assert r.status_code == 404, r.text

        r = integration_client.put(
            f"/api/sessions/{b_sid}", json={"title": "hijack"}, headers=_auth(token_a)
        )
        assert r.status_code == 404, r.text

        r = integration_client.post(
            f"/api/sessions/{b_sid}/messages",
            json={"role": "user", "content": "x"},
            headers=_auth(token_a),
        )
        assert r.status_code == 404, r.text

        r = integration_client.delete(f"/api/sessions/{b_sid}", headers=_auth(token_a))
        assert r.status_code == 404, r.text

        # B can still see it (ownership unchanged).
        r = integration_client.get(f"/api/sessions/{b_sid}", headers=_auth(token_b))
        assert r.status_code == 200, r.text
    finally:
        _cleanup(email_a)
        _cleanup(email_b)
