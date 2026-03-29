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
    PlatformConfig,
    Subscription,
    SubscriptionStatus,
    UsageLog,
    User,
)

# ---------------------------------------------------------------------------
# Default config values (used as fallback if DB row not set)
# ---------------------------------------------------------------------------
_CONFIG_DEFAULTS = {
    "free_tier_daily_limit": lambda: str(settings.FREE_TIER_DAILY_LIMIT),
    "pro_monthly_price_ghs": "99.00",
    "enterprise_monthly_price_ghs": "299.00",
}
from ghana_legal.infrastructure.database import get_session


# ---------------------------------------------------------------------------
# Clerk API Enrichment
# ---------------------------------------------------------------------------

async def clerk_fetch_user(clerk_id: str) -> dict | None:
    """Fetch real name + email for a user from the Clerk Backend API.

    Requires CLERK_SECRET_KEY in .env. Returns None if not configured
    or if the request fails.

    Returns dict with keys: email, first_name, last_name, display_name
    """
    import httpx
    secret_key = settings.CLERK_SECRET_KEY
    if not secret_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://api.clerk.com/v1/users/{clerk_id}",
                headers={"Authorization": f"Bearer {secret_key}"},
            )
        if resp.status_code != 200:
            return None

        data = resp.json()
        primary_email = ""
        for addr in data.get("email_addresses", []):
            if addr.get("id") == data.get("primary_email_address_id"):
                primary_email = addr.get("email_address", "")
                break

        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""
        username = data.get("username") or ""
        display_name = (
            f"{first_name} {last_name}".strip()
            or username
            or primary_email
            or clerk_id
        )

        return {
            "email": primary_email,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "display_name": display_name,
        }
    except Exception as e:
        logger.warning(f"Clerk API fetch failed for {clerk_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

async def get_or_create_user(clerk_id: str, email: str = "") -> User:
    """Get existing user or auto-provision on first API request.

    Also backfills real email for users previously provisioned with
    a placeholder address, using the Clerk Backend API if available.

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
            # Try to fetch real email from Clerk API first
            if not email:
                clerk_data = await clerk_fetch_user(clerk_id)
                if clerk_data:
                    email = clerk_data["email"]

            user = User(
                clerk_id=clerk_id,
                email=email or f"{clerk_id}@placeholder.local",
                plan=PlanType.FREE,
            )
            session.add(user)
            await session.flush()
            logger.info(f"Auto-provisioned new user: {clerk_id} (email={user.email}, plan=free)")

        elif user.email.endswith("@placeholder.local"):
            # Backfill real email for existing placeholder users
            clerk_data = await clerk_fetch_user(clerk_id)
            if clerk_data and clerk_data["email"]:
                user.email = clerk_data["email"]
                user.updated_at = datetime.now(timezone.utc)
                logger.info(f"Backfilled real email for {clerk_id}: {user.email}")

        return user


async def get_user(clerk_id: str) -> User | None:
    """Fetch a user by Clerk ID. Returns None if not found."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Platform Configuration
# ---------------------------------------------------------------------------

async def get_platform_config() -> dict:
    """Fetch all platform config rows from DB, falling back to defaults.

    Returns a typed dict with:
        free_tier_daily_limit (int)
        pro_monthly_price_ghs (float)
        enterprise_monthly_price_ghs (float)
    """
    async with get_session() as session:
        result = await session.execute(select(PlatformConfig))
        rows = {row.key: row.value for row in result.scalars().all()}

    # Merge with defaults for any missing keys
    merged = {}
    for key, default_fn in _CONFIG_DEFAULTS.items():
        raw = rows.get(key)
        if raw is None:
            raw = default_fn() if callable(default_fn) else default_fn
        merged[key] = raw

    return {
        "free_tier_daily_limit": int(merged["free_tier_daily_limit"]),
        "pro_monthly_price_ghs": float(merged["pro_monthly_price_ghs"]),
        "enterprise_monthly_price_ghs": float(merged["enterprise_monthly_price_ghs"]),
    }


async def set_platform_config(updates: dict) -> dict:
    """Upsert one or more config keys into the DB.

    Args:
        updates: dict of key → value pairs to persist.

    Returns:
        The full updated config dict.
    """
    async with get_session() as session:
        for key, value in updates.items():
            if key not in _CONFIG_DEFAULTS:
                raise ValueError(f"Unknown config key: {key}")
            row = await session.get(PlatformConfig, key)
            if row is None:
                row = PlatformConfig(key=key, value=str(value))
                session.add(row)
            else:
                row.value = str(value)
        logger.info(f"Platform config updated: {list(updates.keys())}")

    return await get_platform_config()


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
        # Read limit from DB config (falls back to settings default)
        cfg = await get_platform_config()
        daily_limit = cfg["free_tier_daily_limit"]
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


# ---------------------------------------------------------------------------
# Admin Helpers
# ---------------------------------------------------------------------------

async def switch_user_plan(clerk_id: str, new_plan: PlanType) -> User:
    """Admin override: directly set a user's plan tier.

    Updates the subscription record status when downgrading to free.
    Does NOT create a Paystack subscription (admin manual action).

    Args:
        clerk_id: Clerk user ID.
        new_plan: The target plan tier.

    Returns:
        The updated User instance.
    """
    async with get_session() as session:
        result = await session.execute(select(User).where(User.clerk_id == clerk_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"User not found: {clerk_id}")

        old_plan = user.plan
        user.plan = new_plan
        user.updated_at = datetime.now(timezone.utc)

        # If downgrading to free, cancel active subscriptions
        if new_plan == PlanType.FREE:
            sub_result = await session.execute(
                select(Subscription).where(Subscription.clerk_id == clerk_id)
            )
            for sub in sub_result.scalars().all():
                sub.status = SubscriptionStatus.CANCELLED

        logger.info(f"Admin plan switch: {clerk_id} | {old_plan.value} → {new_plan.value}")
        return user


async def wipe_user_daily_usage(clerk_id: str) -> int:
    """Delete all of today's usage log entries for a user (admin reset).

    Gives a free-tier user a fresh daily allocation immediately.

    Args:
        clerk_id: Clerk user ID.

    Returns:
        Number of usage log rows deleted.
    """
    from sqlalchemy import delete as sa_delete

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    async with get_session() as session:
        result = await session.execute(
            sa_delete(UsageLog).where(
                UsageLog.clerk_id == clerk_id,
                UsageLog.created_at >= today_start,
            ).returning(UsageLog.id)
        )
        deleted = len(result.fetchall())

    logger.info(f"Admin wipe: {deleted} usage rows deleted for {clerk_id}")
    return deleted


async def list_users_with_usage(search: str = "", page: int = 1, per_page: int = 30) -> dict:
    """Fetch a paginated list of users with today's query count.

    Args:
        search: Optional filter on email or clerk_id (case-insensitive substring).
        page: Page number (1-indexed).
        per_page: Rows per page.

    Returns:
        dict with keys: users (list), total (int), page, per_page
    """
    from sqlalchemy import func as sql_func, or_, cast, String

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    async with get_session() as session:
        # Subquery: today's usage count per user
        usage_sub = (
            select(UsageLog.clerk_id, sql_func.count(UsageLog.id).label("used_today"))
            .where(UsageLog.created_at >= today_start)
            .group_by(UsageLog.clerk_id)
            .subquery()
        )

        query = (
            select(User, sql_func.coalesce(usage_sub.c.used_today, 0).label("used_today"))
            .outerjoin(usage_sub, User.clerk_id == usage_sub.c.clerk_id)
        )

        if search:
            query = query.where(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.clerk_id.ilike(f"%{search}%"),
                )
            )

        # Total count
        count_q = select(sql_func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Paginate
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        rows = (await session.execute(query)).all()

    users_out = [
        {
            "clerk_id": row.User.clerk_id,
            "email": row.User.email,
            "plan": row.User.plan.value,
            "used_today": row.used_today,
            "created_at": row.User.created_at.isoformat() if row.User.created_at else None,
            "updated_at": row.User.updated_at.isoformat() if row.User.updated_at else None,
        }
        for row in rows
    ]

    return {"users": users_out, "total": total, "page": page, "per_page": per_page}
