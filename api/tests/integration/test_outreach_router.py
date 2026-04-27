"""Integration tests for /api/outreach endpoints (Phase 1, P1-3 backend).

Real-DB tests — see api/tests/integration/conftest.py for the
TEST_DATABASE_URL contract. Tests skip if the env var isn't set.

Coverage:
  - POST /events writes through and returns the serialized row
  - GET  /events lists with paging + filter combinations
  - GET  /events/{id} 404s on missing / cross-user access
  - DELETE /events/{id} removes only the owner's row
  - GET  /pipeline aggregates per-company status counts
  - Enum validation on status / purpose / channel / perspective
"""

from __future__ import annotations

import uuid


def _fresh_email() -> str:
    return f"it-out-{uuid.uuid4().hex[:8]}@integration.test"


def _fresh_invite_code(cur) -> str:
    code = f"OUT-{uuid.uuid4().hex[:8].upper()}"
    cur.execute(
        "INSERT INTO invite_codes (code, note, max_uses) VALUES (%s, %s, %s)",
        (code, "outreach-integration", 1),
    )
    return code


def _register_user(client, email: str) -> tuple[str, str]:
    """Register a fresh user and return (user_id, bearer_token)."""
    from auth_db import transaction

    with transaction() as cur:
        code = _fresh_invite_code(cur)

    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "name": "Outreach Tester",
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
# Create + read round-trip
# ---------------------------------------------------------------------------


def test_create_then_get_event(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post(
            "/api/outreach/events",
            json={
                "to_company": "AstraZeneca",
                "purpose": "cold_outreach",
                "channel": "email",
                "status": "sent",
                "to_contact": "BD Lead",
                "subject": "KRAS G12D 抑制剂介绍",
                "notes": "first touch",
            },
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["to_company"] == "AstraZeneca"
        assert created["status"] == "sent"
        assert created["created_at"]  # ISO string

        # GET single
        r2 = integration_client.get(f"/api/outreach/events/{created['id']}", headers=_auth(token))
        assert r2.status_code == 200
        assert r2.json()["id"] == created["id"]
    finally:
        _cleanup(email)


def test_list_events_paginates_and_filters(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        # Seed 3 events across 2 companies
        for company, status in [
            ("Pfizer", "sent"),
            ("Pfizer", "replied"),
            ("Merck", "sent"),
        ]:
            integration_client.post(
                "/api/outreach/events",
                json={
                    "to_company": company,
                    "purpose": "cold_outreach",
                    "status": status,
                },
                headers=_auth(token),
            )

        # No filter — should see all 3
        r = integration_client.get("/api/outreach/events", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert len(body["data"]) == 3

        # Filter by company
        r = integration_client.get("/api/outreach/events?company=Pfizer", headers=_auth(token))
        assert r.json()["total"] == 2

        # Filter by status
        r = integration_client.get("/api/outreach/events?status=replied", headers=_auth(token))
        assert r.json()["total"] == 1

        # Pagination
        r = integration_client.get("/api/outreach/events?page=1&page_size=2", headers=_auth(token))
        body = r.json()
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["data"]) == 2
        assert body["total"] == 3
        assert body["total_pages"] == 2
    finally:
        _cleanup(email)


def test_search_matches_subject_and_notes(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        integration_client.post(
            "/api/outreach/events",
            json={
                "to_company": "Novartis",
                "purpose": "cold_outreach",
                "subject": "IRF5 自免管线",
                "notes": "Q2 BD pipeline outreach",
            },
            headers=_auth(token),
        )
        integration_client.post(
            "/api/outreach/events",
            json={"to_company": "BMS", "purpose": "cold_outreach", "notes": "unrelated"},
            headers=_auth(token),
        )

        r = integration_client.get("/api/outreach/events?search=IRF5", headers=_auth(token))
        assert r.json()["total"] == 1
        r = integration_client.get("/api/outreach/events?search=pipeline", headers=_auth(token))
        assert r.json()["total"] == 1
    finally:
        _cleanup(email)


# ---------------------------------------------------------------------------
# Pipeline aggregation
# ---------------------------------------------------------------------------


def test_pipeline_aggregates_per_company(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        for company, status in [
            ("Pfizer", "sent"),
            ("Pfizer", "sent"),
            ("Pfizer", "replied"),
            ("Merck", "sent"),
        ]:
            integration_client.post(
                "/api/outreach/events",
                json={"to_company": company, "purpose": "cold_outreach", "status": status},
                headers=_auth(token),
            )

        r = integration_client.get("/api/outreach/pipeline", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["company_count"] == 2
        assert body["event_count"] == 4

        by_co = {row["company"]: row for row in body["data"]}
        assert by_co["Pfizer"]["statuses"] == {"sent": 2, "replied": 1}
        assert by_co["Pfizer"]["total_events"] == 3
        assert by_co["Merck"]["statuses"] == {"sent": 1}
    finally:
        _cleanup(email)


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


def test_event_is_user_scoped(integration_client):
    """User B must not see / fetch / delete user A's events."""
    email_a = _fresh_email()
    email_b = _fresh_email()
    _, token_a = _register_user(integration_client, email_a)
    _, token_b = _register_user(integration_client, email_b)
    try:
        r = integration_client.post(
            "/api/outreach/events",
            json={"to_company": "Roche", "purpose": "cold_outreach"},
            headers=_auth(token_a),
        )
        event_id = r.json()["id"]

        # B cannot see A's event in list
        r = integration_client.get("/api/outreach/events", headers=_auth(token_b))
        assert r.json()["total"] == 0

        # B cannot fetch A's event by id
        r = integration_client.get(f"/api/outreach/events/{event_id}", headers=_auth(token_b))
        assert r.status_code == 404

        # B cannot delete A's event
        r = integration_client.delete(f"/api/outreach/events/{event_id}", headers=_auth(token_b))
        assert r.status_code == 404

        # A still has it
        r = integration_client.get(f"/api/outreach/events/{event_id}", headers=_auth(token_a))
        assert r.status_code == 200
    finally:
        _cleanup(email_a)
        _cleanup(email_b)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_event(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post(
            "/api/outreach/events",
            json={"to_company": "Sanofi", "purpose": "cold_outreach"},
            headers=_auth(token),
        )
        event_id = r.json()["id"]

        r = integration_client.delete(f"/api/outreach/events/{event_id}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["deleted"] is True

        # Subsequent GET 404s
        r = integration_client.get(f"/api/outreach/events/{event_id}", headers=_auth(token))
        assert r.status_code == 404
    finally:
        _cleanup(email)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_invalid_status_rejected(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post(
            "/api/outreach/events",
            json={"to_company": "GSK", "purpose": "cold_outreach", "status": "frobnicated"},
            headers=_auth(token),
        )
        assert r.status_code == 400
        assert "status" in r.json()["detail"].lower()
    finally:
        _cleanup(email)


def test_empty_company_rejected(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.post(
            "/api/outreach/events",
            json={"to_company": "   ", "purpose": "cold_outreach"},
            headers=_auth(token),
        )
        assert r.status_code == 400
    finally:
        _cleanup(email)


def test_list_filter_invalid_status_rejected(integration_client):
    email = _fresh_email()
    _, token = _register_user(integration_client, email)
    try:
        r = integration_client.get("/api/outreach/events?status=not-real", headers=_auth(token))
        assert r.status_code == 400
    finally:
        _cleanup(email)
