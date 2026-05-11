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
    record_payment,
    update_user_plan_by_clerk_id,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])

PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{reference}"
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

    # 2. Validate amount against current pro price
    amount_ghs = (tx.get("amount") or 0) / 100
    currency = tx.get("currency", "GHS")
    cfg = await get_platform_config()
    expected_ghs = float(cfg["pro_monthly_price_ghs"])
    if amount_ghs + AMOUNT_TOLERANCE_GHS < expected_ghs:
        logger.warning(
            f"Verify: ref={reference} amount GHS {amount_ghs} below expected {expected_ghs}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Amount paid (GHS {amount_ghs}) is less than the Pro plan price (GHS {expected_ghs}).",
        )

    # 3. Ensure the user exists in our DB with their real Clerk email,
    # then upgrade. Lookup is by clerk_id so a stale or placeholder email
    # row can still be upgraded correctly.
    customer_email = (tx.get("customer") or {}).get("email") or ""
    await get_or_create_user(clerk_id=clerk_id, email=customer_email)

    customer_code = (tx.get("customer") or {}).get("customer_code")
    upgraded_user = await update_user_plan_by_clerk_id(
        clerk_id=clerk_id,
        plan=PlanType.PROFESSIONAL,
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
        plan=PlanType.PROFESSIONAL,
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
