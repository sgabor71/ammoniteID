# ============================================================
# stripe_api.py — Stripe Checkout + Webhook
# AmmoniteID
# ============================================================
#
# SETUP:
#   1. pip install stripe
#   2. Set environment variables (or add to .env):
#        STRIPE_SECRET_KEY   = sk_live_...
#        STRIPE_WEBHOOK_SECRET = whsec_...   (from Stripe Dashboard → Webhooks)
#        STRIPE_PRICE_MONTHLY  = price_...   (from Stripe Dashboard → Products)
#        STRIPE_PRICE_ANNUAL   = price_...
#
#   3. In Stripe Dashboard → Webhooks → Add endpoint:
#        URL: https://yourdomain.com/api/stripe/webhook
#        Events to listen: checkout.session.completed
#                          customer.subscription.deleted
# ============================================================

import os
import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import sqlite3

# Import shared database configuration
from database import DB_PATH

stripe_router = APIRouter(prefix="/api/stripe", tags=["stripe"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_MONTHLY  = os.getenv("STRIPE_PRICE_MONTHLY",  "")
STRIPE_PRICE_ANNUAL   = os.getenv("STRIPE_PRICE_ANNUAL",   "")

# ── Base URL for redirect after payment ──────────────────────
# Change to your deployed domain when on Hetzner
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _set_user_tier(uid: str, tier: str):
    """Upgrade or downgrade a user's tier in the DB."""
    conn = _db()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET premium_status = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (tier.upper(), uid)
    )
    conn.commit()
    conn.close()


# ── Models ───────────────────────────────────────────────────
class CheckoutRequest(BaseModel):
    uid:  str        # Firebase UID
    plan: str        # 'monthly' or 'annual'


# ============================================================
# POST /api/stripe/create-checkout-session
# Called by upgrade.html when user clicks Subscribe
# ============================================================
@stripe_router.post("/create-checkout-session")
async def create_checkout_session(body: CheckoutRequest):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured.")

    price_id = STRIPE_PRICE_MONTHLY if body.plan == "monthly" else STRIPE_PRICE_ANNUAL

    if not price_id:
        raise HTTPException(
            status_code=500,
            detail=f"Price ID for '{body.plan}' not set. "
                   "Add STRIPE_PRICE_MONTHLY / STRIPE_PRICE_ANNUAL env vars."
        )

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            # Pass UID so the webhook knows which user to upgrade
            client_reference_id=body.uid,
            metadata={"uid": body.uid, "plan": body.plan},
            success_url=f"{BASE_URL}/static/upgrade-success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/static/upgrade.html?cancelled=1",
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# POST /api/stripe/webhook
# Stripe calls this after payment — upgrades the user
# Add to Stripe Dashboard → Webhooks
# ============================================================
@stripe_router.post("/webhook")
async def stripe_webhook(request: Request):
    payload   = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Verify the webhook came from Stripe
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Payment succeeded → upgrade user ─────────────────────
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        uid = session.get("client_reference_id") or \
              (session.get("metadata") or {}).get("uid")
        if uid:
            _set_user_tier(uid, "PREMIUM")
            print(f"✅ Upgraded user {uid} to PREMIUM")

    # ── Subscription cancelled → downgrade user ───────────────
    elif event["type"] == "customer.subscription.deleted":
        # Map customer ID back to UID if you store it
        # For now log it; full cancel flow can be added later
        sub = event["data"]["object"]
        print(f"⚠️ Subscription cancelled: {sub['id']}")
        # TODO: map sub['customer'] → uid → _set_user_tier(uid, 'FREE')

    return JSONResponse({"status": "ok"})
