"""Stripe integration for subscription management."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from server.database import get_db
from sqlalchemy.orm import Session

LOGGER = logging.getLogger(__name__)

# Stripe configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_PLACEHOLDER")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_PLACEHOLDER")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "price_9p95_monthly")

# Initialize Stripe
try:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    HAS_STRIPE = True
except ImportError:
    LOGGER.warning("Stripe SDK not installed. Run: pip install stripe")
    HAS_STRIPE = False

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


class CheckoutRequest(BaseModel):
    """Request to create checkout session."""
    price_id: Optional[str] = None
    trial_days: int = 3


class SubscriptionStatus(BaseModel):
    """Subscription status response."""
    status: str
    tier: str
    trial_ends_at: Optional[str] = None
    current_period_end: Optional[str] = None


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for subscription."""
    if not HAS_STRIPE:
        raise HTTPException(status_code=503, detail="Payment system not configured")
    
    try:
        # Create checkout session with 3-day trial
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": request.price_id or STRIPE_PRICE_ID,
                "quantity": 1,
            }],
            subscription_data={
                "trial_period_days": request.trial_days,
            },
            success_url="http://localhost:8000/?subscription=success",
            cancel_url="http://localhost:8000/?subscription=canceled",
        )
        
        return {"sessionId": session.id, "url": session.url}
        
    except stripe.error.StripeError as e:
        LOGGER.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events."""
    if not HAS_STRIPE:
        raise HTTPException(status_code=503, detail="Payment system not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        LOGGER.info(f"Checkout completed: {session['id']}")
        # TODO: Update user's subscription status in database
        
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        LOGGER.info(f"Subscription updated: {subscription['id']}")
        # TODO: Sync subscription status
        
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        LOGGER.info(f"Subscription canceled: {subscription['id']}")
        # TODO: Downgrade user to free tier
    
    return {"status": "success"}


@router.get("/subscription-status")
async def get_subscription_status(db: Session = Depends(get_db)):
    """Get current user's subscription status."""
    # TODO: Get from database based on authenticated user
    return SubscriptionStatus(
        status="trialing",
        tier="standard",
        trial_ends_at=(datetime.utcnow() + timedelta(days=3)).isoformat(),
    )
