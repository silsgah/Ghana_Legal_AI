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
    resolve_plan_from_payment,
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


def _parse_metadata(data: dict) -> dict | None:
    """Normalise Paystack's metadata blob (sometimes a JSON string) to a dict.

    Returns None when absent or unparseable so callers can fall back to
    other signals (plan_code, amount).
    """
    metadata = data.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return None
    return metadata if isinstance(metadata, dict) else None


def _extract_clerk_id(data: dict) -> str | None:
    """Pull clerk_id out of Paystack's metadata blob."""
    metadata = _parse_metadata(data)
    if metadata is None:
        return None
    return metadata.get("clerk_id") or None


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
        metadata = _parse_metadata(data)
        # charge.success on a subscription renewal includes the plan code too.
        plan_code = (data.get("plan") or {}).get("plan_code") if isinstance(data.get("plan"), dict) else None

        resolved_plan, source = await resolve_plan_from_payment(
            metadata=metadata, plan_code=plan_code, amount_ghs=amount_ghs,
        )

        logger.info(
            f"Payment success: clerk_id={clerk_id} email={customer_email} "
            f"amount=GHS {amount_ghs} ref={reference} "
            f"resolved_plan={resolved_plan.value if resolved_plan else 'UNRESOLVED'} "
            f"source={source}"
        )

        # Upgrade the user only when we're confident which tier they paid for.
        # Unresolved → record the payment but DO NOT touch the plan column;
        # admin will need to investigate and use the manual switcher.
        if resolved_plan is not None:
            upgraded = False
            if clerk_id:
                user = await update_user_plan_by_clerk_id(
                    clerk_id=clerk_id,
                    plan=resolved_plan,
                    paystack_customer_code=customer_code,
                )
                upgraded = user is not None

            if not upgraded and customer_email:
                await update_user_plan(
                    email=customer_email,
                    plan=resolved_plan,
                    paystack_customer_code=customer_code,
                )
        else:
            logger.warning(
                f"Could not resolve plan for charge.success ref={reference} "
                f"amount=GHS {amount_ghs}. Payment recorded but user plan NOT changed. "
                f"Admin must manually upgrade via /admin Users tab."
            )

        # Record the payment for the admin audit trail. Idempotent on reference,
        # so re-firing the webhook (or the verify endpoint having already
        # written the row) is safe. Use resolved plan when known; otherwise
        # leave as FREE so the audit row signals an unmatched payment.
        if reference:
            await record_payment(
                reference=reference,
                clerk_id=clerk_id,
                email=customer_email or None,
                amount_ghs=amount_ghs,
                currency=data.get("currency", "GHS"),
                status=data.get("status", "success"),
                plan=resolved_plan or PlanType.FREE,
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
        metadata = _parse_metadata(data)
        # Subscription amount lives under plan.amount (pesewas)
        plan_amount = (data.get("plan") or {}).get("amount")
        amount_ghs = (plan_amount / 100) if plan_amount else None

        resolved_plan, source = await resolve_plan_from_payment(
            metadata=metadata, plan_code=plan_code, amount_ghs=amount_ghs,
        )

        logger.info(
            f"Subscription created: clerk_id={clerk_id} email={customer_email} "
            f"plan_code={plan_code} resolved={resolved_plan.value if resolved_plan else 'UNRESOLVED'} "
            f"source={source}"
        )

        if resolved_plan is None:
            logger.warning(
                f"Could not resolve plan for subscription.create plan_code={plan_code!r}. "
                f"Subscription event ignored — admin must manually upgrade. "
                f"Add the plan_code to PlatformConfig (paystack_plan_* fields)."
            )
        else:
            upgraded = False
            if clerk_id:
                user = await update_user_plan_by_clerk_id(
                    clerk_id=clerk_id,
                    plan=resolved_plan,
                    paystack_subscription_code=subscription_code,
                    paystack_customer_code=customer_code,
                )
                upgraded = user is not None

            if not upgraded and customer_email:
                await update_user_plan(
                    email=customer_email,
                    plan=resolved_plan,
                    paystack_subscription_code=subscription_code,
                    paystack_customer_code=customer_code,
                )

    elif event_type == "invoice.payment_failed":
        # A recurring renewal charge failed (expired card, insufficient funds).
        # We deliberately do NOT downgrade immediately — Paystack will retry a
        # few times over several days, and only fire subscription.disable if
        # all retries fail. Log + record so admin can see failed renewals in
        # the payments tab, but the user keeps access during the retry window.
        customer_email = data.get("customer", {}).get("email", "")
        plan_code = (data.get("subscription") or {}).get("plan", {}).get("plan_code") if isinstance(data.get("subscription"), dict) else None
        subscription_code = (data.get("subscription") or {}).get("subscription_code") if isinstance(data.get("subscription"), dict) else None
        amount_ghs = (data.get("amount", 0) or 0) / 100
        reference = data.get("invoice_code") or data.get("offline_reference") or ""
        clerk_id = _extract_clerk_id(data)

        logger.warning(
            f"Renewal payment failed: clerk_id={clerk_id} email={customer_email} "
            f"plan_code={plan_code} subscription={subscription_code} "
            f"amount=GHS {amount_ghs} ref={reference}"
        )

        # Record for the admin audit trail. Plan column is purely informational
        # here — the user's actual plan stays unchanged. We use FREE as a
        # neutral placeholder since we don't always know the original tier on
        # a failed invoice payload.
        if reference:
            await record_payment(
                reference=reference,
                clerk_id=clerk_id,
                email=customer_email or None,
                amount_ghs=amount_ghs,
                currency=data.get("currency", "GHS"),
                status="failed",
                plan=PlanType.FREE,
                paystack_customer_code=data.get("customer", {}).get("customer_code"),
                channel=data.get("channel"),
                source="webhook",
                paid_at=_parse_paid_at(data.get("paid_at")) or datetime.now(timezone.utc),
                raw_response=data,
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
