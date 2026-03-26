"""
Paystack Webhook Handler for Ghana Legal AI SaaS.

Handles subscription events from Paystack to provision/revoke premium access.
"""

import hashlib
import hmac
import os
import json
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from ghana_legal.domain.models import PlanType
from ghana_legal.infrastructure.usage import update_user_plan, cancel_user_subscription

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_paystack_signature(payload: bytes, signature: str) -> bool:
    """Verify the Paystack webhook signature using HMAC SHA-512."""
    secret = os.getenv("PAYSTACK_SECRET_KEY", "")
    computed = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("/paystack")
async def paystack_webhook(request: Request):
    """
    Handle Paystack webhook events.
    
    Supported events:
    - charge.success: User completed a payment
    - subscription.create: User subscribed to a plan
    - subscription.disable: User cancelled subscription
    """
    # Get the raw body and signature
    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    # Verify signature
    if not verify_paystack_signature(payload, signature):
        logger.warning("Invalid Paystack webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the event
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("event", "")
    data = event.get("data", {})

    logger.info(f"Paystack webhook received: {event_type}")

    if event_type == "charge.success":
        # Payment was successful
        customer_email = data.get("customer", {}).get("email", "")
        amount = data.get("amount", 0) / 100  # Paystack sends amount in pesewas
        reference = data.get("reference", "")
        
        logger.info(f"Payment success: {customer_email} paid GHS {amount} (ref: {reference})")
        
        # Provision Pro plan upon successful payment
        await update_user_plan(
            email=customer_email,
            plan=PlanType.PROFESSIONAL,
            paystack_customer_code=data.get("customer", {}).get("customer_code")
        )

    elif event_type == "subscription.create":
        # Subscription created
        customer_email = data.get("customer", {}).get("email", "")
        plan_code = data.get("plan", {}).get("plan_code", "")
        subscription_code = data.get("subscription_code", "")
        
        logger.info(f"Subscription created: {customer_email} -> {plan_code}")
        
        # Map Paystack plan code to internal plan (simplify to Professional for now)
        await update_user_plan(
            email=customer_email,
            plan=PlanType.PROFESSIONAL,
            paystack_subscription_code=subscription_code,
            paystack_customer_code=data.get("customer", {}).get("customer_code")
        )

    elif event_type == "subscription.disable":
        # Subscription cancelled
        customer_email = data.get("customer", {}).get("email", "")
        
        logger.info(f"Subscription cancelled: {customer_email}")
        
        # Revoke premium access
        await cancel_user_subscription(email=customer_email)

    return {"status": "ok"}
