"""
Integration test: register → login → /me against a real Postgres.

Covers the full wiring that unit tests mock out:
  - auth_db connection pool + SQL
  - password hashing + JWT issuance
  - invite-code consumption flow
  - get_current_user's DB lookup
"""

from __future__ import annotations

import uuid


def _fresh_invite_code(cur, note: str = "integration-test") -> str:
    """Insert a single-use invite code directly; return the code string."""
    code = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    cur.execute(
        "INSERT INTO invite_codes (code, note, max_uses) VALUES (%s, %s, %s)",
        (code, note, 1),
    )
    return code


def _fresh_email() -> str:
    return f"it-{uuid.uuid4().hex[:8]}@integration.test"


def test_register_login_me_end_to_end(integration_client):
    """register → login → /me should pass end-to-end against a real DB.

    Owns its cleanup so the DB is left roughly as we found it (one
    invite_code row consumed, one user row deleted).
    """
    from auth_db import transaction

    email = _fresh_email()
    with transaction() as cur:
        code = _fresh_invite_code(cur)

    try:
        # 1. Register
        r = integration_client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "name": "Integration Tester",
                "invite_code": code,
            },
        )
        assert r.status_code == 200, r.text
        register_body = r.json()
        assert register_body["token"]
        assert register_body["user"]["email"] == email
        assert register_body["user"]["name"] == "Integration Tester"
        # hashed_password must never round-trip to the client
        assert "hashed_password" not in register_body["user"]

        # 2. Login with the same credentials — must issue a new token
        r = integration_client.post(
            "/api/auth/login",
            json={"email": email, "password": "correct-horse-battery-staple"},
        )
        assert r.status_code == 200, r.text
        login_body = r.json()
        assert login_body["token"]
        assert login_body["user"]["email"] == email

        # 3. /me with the login token — must round-trip to the user row via DB
        r = integration_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {login_body['token']}"},
        )
        assert r.status_code == 200, r.text
        me_body = r.json()
        assert me_body["email"] == email
        assert me_body["id"] == login_body["user"]["id"]

    finally:
        with transaction() as cur:
            cur.execute("DELETE FROM users WHERE email = %s", (email,))


def test_register_rejects_reused_invite_code(integration_client):
    """A single-use invite code must not register a second user."""
    from auth_db import transaction

    email_a = _fresh_email()
    email_b = _fresh_email()
    with transaction() as cur:
        code = _fresh_invite_code(cur)

    try:
        # First register — succeeds, code consumed.
        r = integration_client.post(
            "/api/auth/register",
            json={
                "email": email_a,
                "password": "hunter22-hunter22",
                "name": "A",
                "invite_code": code,
            },
        )
        assert r.status_code == 200, r.text

        # Second register with same code — must fail.
        r = integration_client.post(
            "/api/auth/register",
            json={
                "email": email_b,
                "password": "hunter22-hunter22",
                "name": "B",
                "invite_code": code,
            },
        )
        assert r.status_code == 400, r.text
        assert "邀请码已被使用" in r.text

    finally:
        with transaction() as cur:
            cur.execute("DELETE FROM users WHERE email IN (%s, %s)", (email_a, email_b))


def test_login_rejects_wrong_password(integration_client):
    """Wrong password on an existing account must 401, not 500."""
    from auth_db import transaction

    email = _fresh_email()
    with transaction() as cur:
        code = _fresh_invite_code(cur)

    try:
        r = integration_client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery-staple",
                "name": "Pw Test",
                "invite_code": code,
            },
        )
        assert r.status_code == 200, r.text

        r = integration_client.post(
            "/api/auth/login",
            json={"email": email, "password": "definitely-wrong"},
        )
        assert r.status_code == 401, r.text

    finally:
        with transaction() as cur:
            cur.execute("DELETE FROM users WHERE email = %s", (email,))
