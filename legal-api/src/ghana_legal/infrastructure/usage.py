"""Usage tracking and quota enforcement for Ghana Legal AI SaaS.

Provides functions to auto-provision users, check free-tier quotas,
log per-query usage, and manage plan upgrades from Paystack webhooks.
"""

from datetime import datetime, timezone, timedelta

from loguru import logger
from sqlalchemy import func, select

from ghana_legal.config import settings
from ghana_legal.domain.models import (
    PlanType,
    Subscription,
    SubscriptionStatus,
    UsageLog,
    User,
)
from ghana_legal.infrastructure.database import get_session


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

async def get_or_create_user(clerk_id: str, email: str = "") -> User:
    """Get existing user or auto-provision on first API request.

    Args:
        clerk_id: Clerk user ID from JWT `sub` claim.
        email: User email (optional, from Clerk JWT or webhook).

    Returns:
        The User ORM instance.
    """
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                clerk_id=clerk_id,
                email=email or f"{clerk_id}@placeholder.local",
                plan=PlanType.FREE,
            )
            session.add(user)
            await session.flush()
            logger.info(f"Auto-provisioned new user: {clerk_id} (plan=free)")

        return user


async def get_user(clerk_id: str) -> User | None:
    """Fetch a user by Clerk ID. Returns None if not found."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Quota Enforcement
# ---------------------------------------------------------------------------

async def check_quota(clerk_id: str) -> dict:
    """Check if a user can make another query.

    Free users are limited to FREE_TIER_DAILY_LIMIT queries per UTC day.
    Professional and Enterprise users have unlimited access.

    Args:
        clerk_id: Clerk user ID.

    Returns:
        dict with keys:
            - allowed (bool): Whether the query is permitted
            - remaining (int): Queries remaining today (-1 for unlimited)
            - plan (str): Current plan name
            - daily_limit (int): The daily limit for the user's plan (-1 for unlimited)
            - used_today (int): Queries used today
    """
    async with get_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            # Auto-provision as free user
            user = User(clerk_id=clerk_id, email=f"{clerk_id}@placeholder.local")
            session.add(user)
            await session.flush()

        # Unlimited for paid plans
        if user.plan in (PlanType.PROFESSIONAL, PlanType.ENTERPRISE):
            return {
                "allowed": True,
                "remaining": -1,
                "plan": user.plan.value,
                "daily_limit": -1,
                "used_today": 0,
            }

        # Count today's queries for free users
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        count_result = await session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.clerk_id == clerk_id,
                UsageLog.created_at >= today_start,
            )
        )
        used_today = count_result.scalar() or 0
        daily_limit = settings.FREE_TIER_DAILY_LIMIT
        remaining = max(0, daily_limit - used_today)

        return {
            "allowed": used_today < daily_limit,
            "remaining": remaining,
            "plan": user.plan.value,
            "daily_limit": daily_limit,
            "used_today": used_today,
        }


# ---------------------------------------------------------------------------
# Usage Logging
# ---------------------------------------------------------------------------

async def log_usage(clerk_id: str, query_text: str, expert_id: str) -> None:
    """Record a query in the usage log.

    Called after the LLM response is initiated (not on quota check).

    Args:
        clerk_id: Clerk user ID.
        query_text: The user's query text.
        expert_id: The expert mode used (constitutional, case_law, etc.).
    """
    async with get_session() as session:
        log_entry = UsageLog(
            clerk_id=clerk_id,
            query_text=query_text,
            expert_id=expert_id,
        )
        session.add(log_entry)
        logger.debug(f"Usage logged: {clerk_id} | expert={expert_id}")


# ---------------------------------------------------------------------------
# Plan Management (called from Paystack webhooks)
# ---------------------------------------------------------------------------

async def update_user_plan(
    email: str,
    plan: PlanType,
    paystack_subscription_code: str | None = None,
    paystack_customer_code: str | None = None,
) -> None:
    """Update a user's plan and create/update subscription record.

    Called from Paystack webhooks when a payment succeeds or
    a subscription is created/cancelled.

    Args:
        email: User email from Paystack event.
        plan: The new plan tier.
        paystack_subscription_code: Paystack subscription code.
        paystack_customer_code: Paystack customer code.
    """
    async with get_session() as session:
        # Find user by email
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning(f"Paystack webhook: No user found for email {email}")
            return

        # Update user plan
        old_plan = user.plan
        user.plan = plan
        user.updated_at = datetime.now(timezone.utc)

        # Create/update subscription record
        if paystack_subscription_code:
            sub_result = await session.execute(
                select(Subscription).where(
                    Subscription.paystack_subscription_code == paystack_subscription_code
                )
            )
            subscription = sub_result.scalar_one_or_none()

            if subscription is None:
                subscription = Subscription(
                    clerk_id=user.clerk_id,
                    paystack_subscription_code=paystack_subscription_code,
                    paystack_customer_code=paystack_customer_code,
                    plan=plan,
                    status=SubscriptionStatus.ACTIVE,
                    started_at=datetime.now(timezone.utc),
                )
                session.add(subscription)
            else:
                subscription.plan = plan
                subscription.status = (
                    SubscriptionStatus.ACTIVE
                    if plan != PlanType.FREE
                    else SubscriptionStatus.CANCELLED
                )

        logger.info(
            f"User plan updated: {user.email} | {old_plan.value} → {plan.value}"
        )


async def cancel_user_subscription(email: str) -> None:
    """Cancel a user's subscription (downgrade to free).

    Called from Paystack subscription.disable webhook.
    """
    await update_user_plan(email=email, plan=PlanType.FREE)
