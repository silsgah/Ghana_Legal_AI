"""Billing endpoints — authoritative server-side payment verification.

The frontend calls `/api/billing/verify-payment` immediately after Paystack's
inline checkout completes. We re-verify with Paystack's API (we can't trust
the browser's claim of success), then upgrade the user's plan keyed by their
authenticated Clerk ID — not by the email Paystack returns, which can
mismatch for users provisioned with placeholder addresses.
"""

import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from ghana_legal.domain.models import PlanType
from ghana_legal.infrastructure.auth import get_current_user
from ghana_legal.infrastructure.usage import (
    check_quota,
    get_or_create_user,
    get_platform_config,
    price_for_plan,
    record_payment,
    resolve_plan_from_payment,
    update_user_plan_by_clerk_id,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])

PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{reference}"
PAYSTACK_MANAGE_LINK_URL = "https://api.paystack.co/subscription/{code}/manage/link"
# Tolerance for legitimate price drift / config updates between checkout and
# verification. 1 GHS is well below the smallest meaningful pricing change.
AMOUNT_TOLERANCE_GHS = 1.0


class VerifyPaymentRequest(BaseModel):
    reference: str


def _parse_paid_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/verify-payment")
async def verify_payment(
    body: VerifyPaymentRequest,
    user: dict = Depends(get_current_user),
):
    """Verify a Paystack transaction and upgrade the authenticated user.

    Flow:
      1. Call Paystack's verify API with the server secret key.
      2. Require status == "success" and amount within tolerance of pro price.
      3. Upgrade the user (lookup by clerk_id — never email).
      4. Persist a Payment audit row.
      5. Return fresh quota so the client can refresh its state.
    """
    secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not secret_key:
        logger.error("PAYSTACK_SECRET_KEY is not configured")
        raise HTTPException(
            status_code=500,
            detail="Payment verification is not configured on the server.",
        )

    clerk_id = user.get("sub")
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Missing user identity")

    reference = body.reference.strip()
    if not reference:
        raise HTTPException(status_code=422, detail="Reference is required")

    # 1. Verify with Paystack
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                PAYSTACK_VERIFY_URL.format(reference=reference),
                headers={"Authorization": f"Bearer {secret_key}"},
            )
    except httpx.RequestError as e:
        logger.error(f"Paystack verify request failed: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Paystack to verify payment")

    if resp.status_code != 200:
        logger.warning(
            f"Paystack verify returned {resp.status_code} for ref={reference}: {resp.text[:200]}"
        )
        raise HTTPException(
            status_code=502,
            detail="Paystack rejected the verification request.",
        )

    payload = resp.json()
    if not payload.get("status"):
        raise HTTPException(
            status_code=400,
            detail=payload.get("message", "Paystack could not verify this reference."),
        )

    tx = payload.get("data") or {}
    tx_status = tx.get("status")
    if tx_status != "success":
        logger.info(f"Verify: ref={reference} not successful (status={tx_status})")
        raise HTTPException(
            status_code=400,
            detail=f"Payment not successful (status: {tx_status}).",
        )

    # 2. Identify which tier the customer actually paid for.
    amount_ghs = (tx.get("amount") or 0) / 100
    currency = tx.get("currency", "GHS")

    # Metadata is the highest-fidelity signal — set by the frontend at
    # checkout-init time. Paystack returns it untouched in the verify response.
    metadata = tx.get("metadata") if isinstance(tx.get("metadata"), dict) else None
    plan_code = (tx.get("plan") or {}).get("plan_code") if isinstance(tx.get("plan"), dict) else None

    resolved_plan, source = await resolve_plan_from_payment(
        metadata=metadata, plan_code=plan_code, amount_ghs=amount_ghs,
    )

    if resolved_plan is None:
        logger.warning(
            f"Verify: ref={reference} amount=GHS {amount_ghs} could not be resolved "
            f"to any tier (metadata={bool(metadata)} plan_code={plan_code!r}). "
            f"Refusing to upgrade until admin investigates."
        )
        raise HTTPException(
            status_code=400,
            detail="We could not match this payment to a plan tier. Contact support with your payment reference.",
        )

    # Cross-check the amount: confirm what was paid matches the resolved
    # plan's configured price. Prevents a metadata-forged "I paid for
    # Institution" attack when the actual amount is GHS 50.
    cycle_hint = (metadata or {}).get("cycle") if metadata else None
    expected_ghs = await price_for_plan(resolved_plan, cycle_hint)
    if amount_ghs + AMOUNT_TOLERANCE_GHS < expected_ghs:
        logger.warning(
            f"Verify: ref={reference} amount=GHS {amount_ghs} below expected "
            f"GHS {expected_ghs} for plan={resolved_plan.value} cycle={cycle_hint!r} "
            f"(resolver source={source})"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Amount paid (GHS {amount_ghs}) is less than the {resolved_plan.value.title()} plan price (GHS {expected_ghs}).",
        )

    logger.info(
        f"Verify: ref={reference} resolved_plan={resolved_plan.value} source={source} "
        f"amount=GHS {amount_ghs} expected=GHS {expected_ghs}"
    )

    # 3. Ensure the user exists in our DB with their real Clerk email,
    # then upgrade. Lookup is by clerk_id so a stale or placeholder email
    # row can still be upgraded correctly.
    customer_email = (tx.get("customer") or {}).get("email") or ""
    await get_or_create_user(clerk_id=clerk_id, email=customer_email)

    customer_code = (tx.get("customer") or {}).get("customer_code")
    upgraded_user = await update_user_plan_by_clerk_id(
        clerk_id=clerk_id,
        plan=resolved_plan,
        paystack_customer_code=customer_code,
    )
    if upgraded_user is None:
        logger.error(f"Verify: user {clerk_id} not found after get_or_create")
        raise HTTPException(status_code=500, detail="Failed to upgrade user account.")

    # 4. Record the payment (idempotent on reference)
    await record_payment(
        reference=reference,
        clerk_id=clerk_id,
        email=customer_email or upgraded_user.email,
        amount_ghs=amount_ghs,
        currency=currency,
        status=tx_status,
        plan=resolved_plan,
        paystack_customer_code=customer_code,
        channel=tx.get("channel"),
        source="verify_endpoint",
        paid_at=_parse_paid_at(tx.get("paid_at")) or datetime.now(timezone.utc),
        raw_response=tx,
    )

    # 5. Return fresh quota
    quota = await check_quota(clerk_id)
    return {
        "success": True,
        "reference": reference,
        "plan": upgraded_user.plan.value,
        "amount_ghs": amount_ghs,
        "quota": quota,
    }


@router.post("/manage-subscription")
async def manage_subscription(user: dict = Depends(get_current_user)):
    """Return a Paystack-hosted URL where the customer can manage their subscription.

    On Paystack's hosted page the customer can:
      - cancel the subscription (which fires the subscription.disable webhook,
        and our handler downgrades them to FREE)
      - update the saved card used for renewals

    We deliberately avoid implementing our own cancel/update UI: Paystack's
    page is PCI-compliant for card updates, and using their flow means we
    only have to react to the resulting webhook instead of tracking the
    email_token they require for direct subscription/disable API calls.
    """
    from sqlalchemy import select
    from ghana_legal.domain.models import Subscription, SubscriptionStatus
    from ghana_legal.infrastructure.database import get_session

    secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not secret_key:
        raise HTTPException(status_code=500, detail="Payment management is not configured on the server.")

    clerk_id = user.get("sub")
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Missing user identity")

    # Find the most-recently-created active subscription for this user.
    async with get_session() as session:
        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.clerk_id == clerk_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.paystack_subscription_code.is_not(None),
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        subscription = result.scalar_one_or_none()

    if subscription is None or not subscription.paystack_subscription_code:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found. If you paid recently, please wait a moment for Paystack to send the confirmation.",
        )

    # Ask Paystack to mint a management URL for this subscription.
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                PAYSTACK_MANAGE_LINK_URL.format(code=subscription.paystack_subscription_code),
                headers={"Authorization": f"Bearer {secret_key}"},
            )
    except httpx.RequestError as e:
        logger.error(f"Paystack manage-link request failed: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Paystack to fetch the management link.")

    if resp.status_code != 200:
        logger.warning(f"Paystack manage-link {resp.status_code} for sub={subscription.paystack_subscription_code}: {resp.text[:200]}")
        raise HTTPException(status_code=502, detail="Paystack rejected the management-link request.")

    payload = resp.json()
    link = (payload.get("data") or {}).get("link")
    if not link:
        raise HTTPException(status_code=502, detail="Paystack did not return a management link.")

    return {"link": link, "subscription_code": subscription.paystack_subscription_code}
