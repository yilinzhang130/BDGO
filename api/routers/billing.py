"""
Stripe billing router  (P2-08).

Endpoints:
  POST /api/billing/checkout          — create a Stripe Checkout Session
  POST /api/billing/webhook           — receive Stripe webhook events (raw body)
  GET  /api/billing/subscription      — current plan + status for authed user

Design notes:
  - All endpoints degrade gracefully when STRIPE_SECRET_KEY is unset:
    they return HTTP 503 with a clear message so the rest of the app
    keeps working in dev/staging without a Stripe account.
  - The webhook is intentionally unauthenticated (Stripe signs the body
    with STRIPE_WEBHOOK_SECRET; we verify that signature before acting).
  - On checkout.session.completed we:
      1. Upsert the subscriptions row
      2. Grant the plan's monthly credit allowance
  - Plan IDs accepted by the checkout endpoint:  "team" | "pro"
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import auth_db
import credits
from auth import get_current_user
from config import (
    STRIPE_PRICE_PRO,
    STRIPE_PRICE_TEAM,
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

# ─────────────────────────────────────────────────────────────
# Plan catalogue
# ─────────────────────────────────────────────────────────────

PLANS: dict[str, dict] = {
    "team": {
        "name": "团队版",
        "price_id": STRIPE_PRICE_TEAM,
        "credits_monthly": 50_000,  # ≈ 500 AI queries at average cost
    },
    "pro": {
        "name": "专业版",
        "price_id": STRIPE_PRICE_PRO,
        "credits_monthly": 500_000,  # effectively unlimited for most teams
    },
}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _stripe_client():
    """Return a configured stripe module or raise 503."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Billing not configured — STRIPE_SECRET_KEY is missing")
    try:
        import stripe as _stripe  # lazy import: keeps startup fast when key absent

        _stripe.api_key = STRIPE_SECRET_KEY
        return _stripe
    except ImportError as exc:
        raise HTTPException(503, "stripe library not installed") from exc


def _upsert_subscription(
    user_id: str,
    plan: str,
    status: str,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    credits_monthly: int,
    current_period_end: datetime | None,
    cancel_at_period_end: bool = False,
) -> None:
    """Create or update the subscriptions row for this user."""
    with auth_db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO subscriptions (
                    user_id, stripe_customer_id, stripe_subscription_id,
                    plan, status, credits_monthly, current_period_end,
                    cancel_at_period_end, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    stripe_customer_id     = COALESCE(EXCLUDED.stripe_customer_id,
                                                      subscriptions.stripe_customer_id),
                    stripe_subscription_id = COALESCE(EXCLUDED.stripe_subscription_id,
                                                      subscriptions.stripe_subscription_id),
                    plan                   = EXCLUDED.plan,
                    status                 = EXCLUDED.status,
                    credits_monthly        = EXCLUDED.credits_monthly,
                    current_period_end     = EXCLUDED.current_period_end,
                    cancel_at_period_end   = EXCLUDED.cancel_at_period_end,
                    updated_at             = NOW()
                """,
            (
                user_id,
                stripe_customer_id,
                stripe_subscription_id,
                plan,
                status,
                credits_monthly,
                current_period_end,
                cancel_at_period_end,
            ),
        )
        conn.commit()


def _get_subscription(user_id: str) -> dict | None:
    with auth_db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT plan, status, credits_monthly, current_period_end,
                       cancel_at_period_end, stripe_customer_id,
                       stripe_subscription_id, updated_at
                FROM subscriptions WHERE user_id = %s
                """,
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    cols = [
        "plan",
        "status",
        "credits_monthly",
        "current_period_end",
        "cancel_at_period_end",
        "stripe_customer_id",
        "stripe_subscription_id",
        "updated_at",
    ]
    return dict(zip(cols, row))


# ─────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan_id: str  # "team" | "pro"
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    credits_monthly: int
    current_period_end: str | None
    cancel_at_period_end: bool
    stripe_subscription_id: str | None
    publishable_key: str


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout_session(
    body: CheckoutRequest,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout Session and return the redirect URL."""
    # Check key first so the error message is always actionable
    stripe = _stripe_client()

    plan = PLANS.get(body.plan_id)
    if not plan:
        raise HTTPException(400, f"Unknown plan '{body.plan_id}'. Valid: {list(PLANS)}")
    if not plan["price_id"]:
        raise HTTPException(
            503,
            f"Stripe price not configured for plan '{body.plan_id}' "
            f"(set STRIPE_PRICE_{body.plan_id.upper()} in env)",
        )

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan["price_id"], "quantity": 1}],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            client_reference_id=user["id"],
            customer_email=user.get("email"),
            metadata={"plan_id": body.plan_id, "user_id": user["id"]},
        )
    except stripe.StripeError as exc:
        logger.error("Stripe checkout error: %s", exc)
        raise HTTPException(502, "Stripe returned an error — please try again") from exc

    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(user: dict = Depends(get_current_user)):
    """Return current subscription details for the authenticated user."""
    row = _get_subscription(user["id"])
    period_end = None
    if row and row.get("current_period_end"):
        dt = row["current_period_end"]
        period_end = dt.isoformat() if isinstance(dt, datetime) else str(dt)

    return SubscriptionResponse(
        plan=row["plan"] if row else "free",
        status=row["status"] if row else "active",
        credits_monthly=row["credits_monthly"] if row else 0,
        current_period_end=period_end,
        cancel_at_period_end=row["cancel_at_period_end"] if row else False,
        stripe_subscription_id=row.get("stripe_subscription_id") if row else None,
        publishable_key=STRIPE_PUBLISHABLE_KEY,
    )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Receive and verify Stripe webhook events.

    Stripe sends the raw request body with a Stripe-Signature header.
    We verify the signature before processing any event.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Webhook not configured — STRIPE_WEBHOOK_SECRET is missing")

    stripe = _stripe_client()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(400, "Invalid Stripe signature") from exc
    except Exception as exc:
        logger.error("Stripe webhook parse error: %s", exc)
        raise HTTPException(400, "Malformed Stripe event") from exc

    _handle_event(stripe, event)
    return {"received": True}


def _handle_event(stripe, event: dict) -> None:  # noqa: ANN001
    """Dispatch Stripe events to the appropriate handler."""
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        _on_checkout_completed(data)
    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        _on_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        _on_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        _on_payment_failed(data)
    else:
        logger.debug("Unhandled Stripe event: %s", event_type)


def _on_checkout_completed(session: dict) -> None:
    """A Stripe Checkout Session completed successfully."""
    user_id = session.get("metadata", {}).get("user_id")
    plan_id = session.get("metadata", {}).get("plan_id", "team")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        logger.error("checkout.session.completed missing user_id in metadata")
        return

    plan = PLANS.get(plan_id, PLANS["team"])
    _upsert_subscription(
        user_id=user_id,
        plan=plan_id,
        status="active",
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        credits_monthly=plan["credits_monthly"],
        current_period_end=None,  # will be filled by subscription.updated event
    )

    # Grant the monthly credit allowance on subscription activation
    try:
        credits.grant_credits(
            user_id,
            plan["credits_monthly"],
            reason=f"Stripe subscription activated — {plan['name']}",
        )
        logger.info(
            "Granted %d credits to user %s (plan=%s)", plan["credits_monthly"], user_id, plan_id
        )
    except Exception as exc:
        logger.error("Failed to grant credits after checkout: %s", exc)


def _on_subscription_updated(sub: dict) -> None:
    """Subscription changed (plan switch, renewal, etc.)."""
    customer_id = sub.get("customer")
    subscription_id = sub.get("id")
    status = sub.get("status", "active")
    cancel_at_period_end = sub.get("cancel_at_period_end", False)

    # Resolve period end
    current_period_end = None
    if sub.get("current_period_end"):
        current_period_end = datetime.fromtimestamp(sub["current_period_end"], tz=UTC)

    # Resolve plan from price metadata or items
    plan_id = "team"
    items = sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        if price_id == STRIPE_PRICE_PRO:
            plan_id = "pro"

    plan = PLANS.get(plan_id, PLANS["team"])

    # Look up user_id by stripe_customer_id
    user_id = _user_id_by_customer(customer_id)
    if not user_id:
        logger.warning("subscription.updated: no user for customer %s", customer_id)
        return

    _upsert_subscription(
        user_id=user_id,
        plan=plan_id,
        status=status,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        credits_monthly=plan["credits_monthly"],
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )


def _on_subscription_deleted(sub: dict) -> None:
    """Subscription cancelled — revert user to free tier."""
    customer_id = sub.get("customer")
    user_id = _user_id_by_customer(customer_id)
    if not user_id:
        return
    _upsert_subscription(
        user_id=user_id,
        plan="free",
        status="canceled",
        stripe_customer_id=customer_id,
        stripe_subscription_id=sub.get("id"),
        credits_monthly=0,
        current_period_end=None,
    )
    logger.info("Subscription canceled for user %s", user_id)


def _on_payment_failed(invoice: dict) -> None:
    """Invoice payment failed — mark subscription past_due."""
    customer_id = invoice.get("customer")
    user_id = _user_id_by_customer(customer_id)
    if not user_id:
        return
    with auth_db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE subscriptions SET status='past_due', updated_at=NOW() WHERE user_id=%s",
            (user_id,),
        )
        conn.commit()
    logger.warning("Payment failed for user %s", user_id)


def _user_id_by_customer(stripe_customer_id: str | None) -> str | None:
    """Resolve a Stripe customer ID to our internal user_id."""
    if not stripe_customer_id:
        return None
    with auth_db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id FROM subscriptions WHERE stripe_customer_id = %s",
            (stripe_customer_id,),
        )
        row = cur.fetchone()
    return str(row[0]) if row else None
