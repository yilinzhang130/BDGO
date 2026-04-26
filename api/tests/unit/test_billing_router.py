"""Unit tests for the Stripe billing router (P2-08).

Tests cover:
  1. Plan catalogue contains team + pro with required fields
  2. Plan credits are positive
  3. checkout returns 503 when STRIPE_SECRET_KEY is absent
  4. checkout returns 400 for unknown plan_id
  5. checkout returns 503 when plan price_id is not configured
  6. checkout creates a Stripe session and returns redirect URL (mocked)
  7. subscription returns free-tier defaults when no DB row
  8. subscription returns stored plan data
  9. webhook returns 503 when STRIPE_WEBHOOK_SECRET is absent
 10. webhook returns 400 on invalid signature
 11. webhook returns 400 on malformed body
 12. checkout.session.completed → upserts subscription
 13. customer.subscription.deleted → reverts to free tier
 14. _handle_event ignores unknown event types gracefully
 15. _user_id_by_customer returns None for missing customer
 16. Config exports STRIPE_ keys
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────
# 1-2. Plan catalogue
# ─────────────────────────────────────────────────────────────


def test_plan_catalogue_has_team_and_pro():
    from routers.billing import PLANS

    assert "team" in PLANS
    assert "pro" in PLANS
    for plan in PLANS.values():
        assert "name" in plan
        assert "credits_monthly" in plan
        assert "price_id" in plan


def test_plan_credits_positive():
    from routers.billing import PLANS

    for name, plan in PLANS.items():
        assert plan["credits_monthly"] > 0, f"{name} credits_monthly must be > 0"


# ─────────────────────────────────────────────────────────────
# 3-6. checkout — validation + Stripe mock
# ─────────────────────────────────────────────────────────────


def test_checkout_503_when_no_stripe_key(client, ext_headers):
    """Missing STRIPE_SECRET_KEY → 503."""
    with patch("routers.billing.STRIPE_SECRET_KEY", ""):
        resp = client.post(
            "/api/billing/checkout",
            headers=ext_headers,
            json={
                "plan_id": "team",
                "success_url": "https://example.com/ok",
                "cancel_url": "https://example.com/cancel",
            },
        )
    assert resp.status_code == 503
    assert "STRIPE_SECRET_KEY" in resp.json()["detail"]


def test_checkout_400_unknown_plan(client, ext_headers):
    fake_stripe = MagicMock()
    fake_stripe.StripeError = Exception
    with (
        patch("routers.billing.STRIPE_SECRET_KEY", "sk_test_fake"),
        patch("routers.billing._stripe_client", return_value=fake_stripe),
    ):
        resp = client.post(
            "/api/billing/checkout",
            headers=ext_headers,
            json={
                "plan_id": "enterprise_xyz",
                "success_url": "https://x.com/ok",
                "cancel_url": "https://x.com/cancel",
            },
        )
    assert resp.status_code == 400
    assert "enterprise_xyz" in resp.json()["detail"]


def test_checkout_503_when_price_id_not_configured(client, ext_headers):
    fake_stripe = MagicMock()
    fake_stripe.StripeError = Exception
    with (
        patch("routers.billing.STRIPE_SECRET_KEY", "sk_test_fake"),
        patch("routers.billing._stripe_client", return_value=fake_stripe),
        patch(
            "routers.billing.PLANS",
            {"team": {"name": "T", "price_id": "", "credits_monthly": 1000}},
        ),
    ):
        resp = client.post(
            "/api/billing/checkout",
            headers=ext_headers,
            json={
                "plan_id": "team",
                "success_url": "https://x.com/ok",
                "cancel_url": "https://x.com/cancel",
            },
        )
    assert resp.status_code == 503
    assert "STRIPE_PRICE_TEAM" in resp.json()["detail"]


def test_checkout_creates_stripe_session(client, ext_headers):
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/cs_test_abc123"
    fake_session.id = "cs_test_abc123"

    fake_stripe = MagicMock()
    fake_stripe.checkout.Session.create.return_value = fake_session
    # Prevent StripeError from being referenced on the real missing module
    fake_stripe.StripeError = Exception

    with (
        patch("routers.billing.STRIPE_SECRET_KEY", "sk_test_fake"),
        patch(
            "routers.billing.PLANS",
            {"team": {"name": "T", "price_id": "price_team_123", "credits_monthly": 50000}},
        ),
        patch("routers.billing._stripe_client", return_value=fake_stripe),
    ):
        resp = client.post(
            "/api/billing/checkout",
            headers=ext_headers,
            json={
                "plan_id": "team",
                "success_url": "https://x.com/ok",
                "cancel_url": "https://x.com/cancel",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "checkout.stripe.com" in data["checkout_url"]
    assert data["session_id"] == "cs_test_abc123"


# ─────────────────────────────────────────────────────────────
# 7-8. subscription endpoint
# ─────────────────────────────────────────────────────────────


def test_subscription_returns_free_when_no_row(client, ext_headers):
    with patch("routers.billing._get_subscription", return_value=None):
        resp = client.get("/api/billing/subscription", headers=ext_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "free"
    assert data["status"] == "active"
    assert data["credits_monthly"] == 0
    assert data["cancel_at_period_end"] is False
    assert data["stripe_subscription_id"] is None


def test_subscription_returns_stored_plan(client, ext_headers):
    stored = {
        "plan": "pro",
        "status": "active",
        "credits_monthly": 500_000,
        "current_period_end": None,
        "cancel_at_period_end": False,
        "stripe_customer_id": "cus_abc",
        "stripe_subscription_id": "sub_xyz",
        "updated_at": None,
    }
    with patch("routers.billing._get_subscription", return_value=stored):
        resp = client.get("/api/billing/subscription", headers=ext_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "pro"
    assert data["credits_monthly"] == 500_000
    assert data["stripe_subscription_id"] == "sub_xyz"


# ─────────────────────────────────────────────────────────────
# 9-11. webhook guards
# ─────────────────────────────────────────────────────────────


def test_webhook_503_when_no_secret(client):
    with patch("routers.billing.STRIPE_WEBHOOK_SECRET", ""):
        resp = client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 503


def test_webhook_400_on_invalid_signature(client):
    """Bad signature → 400, not 500."""

    # Create a fake SignatureVerificationError without importing real stripe
    class FakeSigError(Exception):
        def __init__(self, msg, sig_header):
            super().__init__(msg)

    fake_stripe = MagicMock()
    fake_stripe.SignatureVerificationError = FakeSigError
    fake_stripe.Webhook.construct_event.side_effect = FakeSigError("bad sig", "header")

    with (
        patch("routers.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"),
        patch("routers.billing.STRIPE_SECRET_KEY", "sk_test_fake"),
        patch("routers.billing._stripe_client", return_value=fake_stripe),
    ):
        resp = client.post(
            "/api/billing/webhook",
            content=b'{"type":"test"}',
            headers={"stripe-signature": "t=1,v1=badsig"},
        )
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


def test_webhook_400_on_malformed_body(client):
    fake_stripe = MagicMock()
    fake_stripe.SignatureVerificationError = Exception  # won't be raised
    fake_stripe.Webhook.construct_event.side_effect = ValueError("bad json")

    with (
        patch("routers.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"),
        patch("routers.billing.STRIPE_SECRET_KEY", "sk_test_fake"),
        patch("routers.billing._stripe_client", return_value=fake_stripe),
    ):
        resp = client.post(
            "/api/billing/webhook",
            content=b"NOT JSON",
            headers={"stripe-signature": "t=1,v1=sig"},
        )
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# 12. checkout.session.completed handler
# ─────────────────────────────────────────────────────────────


def test_on_checkout_completed_upserts_subscription():
    session_data = {
        "metadata": {"user_id": "user-001", "plan_id": "team"},
        "customer": "cus_abc",
        "subscription": "sub_xyz",
    }

    with (
        patch("routers.billing._upsert_subscription") as mock_upsert,
        patch("routers.billing.credits") as mock_credits,
    ):
        mock_credits.grant_credits = MagicMock()
        from routers.billing import _on_checkout_completed

        _on_checkout_completed(session_data)

    mock_upsert.assert_called_once()
    # Verify user_id made it through
    args = mock_upsert.call_args
    assert args.kwargs.get("user_id") == "user-001" or (args.args and args.args[0] == "user-001")


# ─────────────────────────────────────────────────────────────
# 13. subscription.deleted reverts to free
# ─────────────────────────────────────────────────────────────


def test_on_subscription_deleted_reverts_to_free():
    sub_data = {"customer": "cus_abc", "id": "sub_xyz"}

    with (
        patch("routers.billing._user_id_by_customer", return_value="user-001"),
        patch("routers.billing._upsert_subscription") as mock_upsert,
    ):
        from routers.billing import _on_subscription_deleted

        _on_subscription_deleted(sub_data)

    mock_upsert.assert_called_once()
    kwargs = mock_upsert.call_args.kwargs
    assert kwargs["plan"] == "free"
    assert kwargs["status"] == "canceled"
    assert kwargs["credits_monthly"] == 0


# ─────────────────────────────────────────────────────────────
# 14. Unknown event types are silently ignored
# ─────────────────────────────────────────────────────────────


def test_handle_event_ignores_unknown():
    from routers.billing import _handle_event

    fake_stripe = MagicMock()
    event = {"type": "totally.unknown.event", "data": {"object": {}}}
    _handle_event(fake_stripe, event)  # must not raise


# ─────────────────────────────────────────────────────────────
# 15. _user_id_by_customer returns None for missing customer
# ─────────────────────────────────────────────────────────────


def test_user_id_by_customer_returns_none_for_none():
    from routers.billing import _user_id_by_customer

    assert _user_id_by_customer(None) is None


def test_user_id_by_customer_returns_none_for_empty():
    from routers.billing import _user_id_by_customer

    assert _user_id_by_customer("") is None


# ─────────────────────────────────────────────────────────────
# 16. Config exports STRIPE_ keys
# ─────────────────────────────────────────────────────────────


def test_config_exports_stripe_keys():
    import config

    for attr in (
        "STRIPE_SECRET_KEY",
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_TEAM",
        "STRIPE_PRICE_PRO",
    ):
        assert hasattr(config, attr), f"config.{attr} missing"
        assert isinstance(getattr(config, attr), str)
