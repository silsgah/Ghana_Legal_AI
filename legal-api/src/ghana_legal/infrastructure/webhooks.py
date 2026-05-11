"""
Paystack Webhook Handler for Ghana Legal AI SaaS.

Handles subscription events from Paystack to provision/revoke premium access.
"""

import hashlib
import hmac
import os
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from ghana_legal.domain.models import PlanType
from ghana_legal.infrastructure.usage import (
    cancel_user_subscription,
    record_payment,
    update_user_plan,
    update_user_plan_by_clerk_id,
)

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


def _extract_clerk_id(data: dict) -> str | None:
    """Pull clerk_id out of Paystack's metadata blob.

    Paystack delivers metadata either as a JSON-encoded string (legacy) or
    as an object (current). Handle both. Returns None when absent so the
    caller can fall back to email lookup.
    """
    metadata = data.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return None
    if isinstance(metadata, dict):
        return metadata.get("clerk_id") or None
    return None


def _parse_paid_at(value: str | None) -> datetime | None:
    """Parse Paystack's ISO timestamps to a tz-aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
        customer_email = data.get("customer", {}).get("email", "")
        amount_ghs = data.get("amount", 0) / 100  # Paystack sends amount in pesewas
        reference = data.get("reference", "")
        customer_code = data.get("customer", {}).get("customer_code")
        clerk_id = _extract_clerk_id(data)

        logger.info(
            f"Payment success: clerk_id={clerk_id} email={customer_email} "
            f"amount=GHS {amount_ghs} ref={reference}"
        )

        # Prefer clerk_id; fall back to email. Email lookup fails for users
        # who were auto-provisioned with a placeholder address.
        upgraded = False
        if clerk_id:
            user = await update_user_plan_by_clerk_id(
                clerk_id=clerk_id,
                plan=PlanType.PROFESSIONAL,
                paystack_customer_code=customer_code,
            )
            upgraded = user is not None

        if not upgraded and customer_email:
            await update_user_plan(
                email=customer_email,
                plan=PlanType.PROFESSIONAL,
                paystack_customer_code=customer_code,
            )

        # Record the payment for the admin audit trail. Idempotent on reference,
        # so re-firing the webhook (or the verify endpoint having already
        # written the row) is safe.
        if reference:
            await record_payment(
                reference=reference,
                clerk_id=clerk_id,
                email=customer_email or None,
                amount_ghs=amount_ghs,
                currency=data.get("currency", "GHS"),
                status=data.get("status", "success"),
                plan=PlanType.PROFESSIONAL,
                paystack_customer_code=customer_code,
                channel=data.get("channel"),
                source="webhook",
                paid_at=_parse_paid_at(data.get("paid_at")) or datetime.now(timezone.utc),
                raw_response=data,
            )

    elif event_type == "subscription.create":
        customer_email = data.get("customer", {}).get("email", "")
        plan_code = data.get("plan", {}).get("plan_code", "")
        subscription_code = data.get("subscription_code", "")
        customer_code = data.get("customer", {}).get("customer_code")
        clerk_id = _extract_clerk_id(data)

        logger.info(
            f"Subscription created: clerk_id={clerk_id} email={customer_email} -> {plan_code}"
        )

        upgraded = False
        if clerk_id:
            user = await update_user_plan_by_clerk_id(
                clerk_id=clerk_id,
                plan=PlanType.PROFESSIONAL,
                paystack_subscription_code=subscription_code,
                paystack_customer_code=customer_code,
            )
            upgraded = user is not None

        if not upgraded and customer_email:
            await update_user_plan(
                email=customer_email,
                plan=PlanType.PROFESSIONAL,
                paystack_subscription_code=subscription_code,
                paystack_customer_code=customer_code,
            )

    elif event_type == "subscription.disable":
        customer_email = data.get("customer", {}).get("email", "")
        clerk_id = _extract_clerk_id(data)

        logger.info(f"Subscription cancelled: clerk_id={clerk_id} email={customer_email}")

        downgraded = False
        if clerk_id:
            user = await update_user_plan_by_clerk_id(
                clerk_id=clerk_id,
                plan=PlanType.FREE,
            )
            downgraded = user is not None

        if not downgraded and customer_email:
            await cancel_user_subscription(email=customer_email)

    return {"status": "ok"}
