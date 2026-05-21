"""Usage tracking and quota enforcement for Ghana Legal AI SaaS.

Provides functions to auto-provision users, check free-tier quotas,
log per-query usage, and manage plan upgrades from Paystack webhooks.
"""

from datetime import datetime, timezone, timedelta

from loguru import logger
from sqlalchemy import func, select

from ghana_legal.config import settings
from ghana_legal.domain.models import (
    Payment,
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
# Per-tier daily query limits. -1 means unlimited.
# Monthly + yearly prices in GHS. Yearly prices reflect a discount.
# Paystack plan codes are populated by the admin after creating Plans in the
# Paystack dashboard (looks like PLN_xxxxxxxx). Empty default = "not yet
# configured" — payments matching this tier will fall back to amount-matching.
_CONFIG_DEFAULTS = {
    # Daily limits
    "free_tier_daily_limit": lambda: str(settings.FREE_TIER_DAILY_LIMIT),
    "student_daily_limit": "50",
    "professional_daily_limit": "-1",
    "firm_daily_limit": "-1",
    "institution_daily_limit": "-1",
    # Monthly prices
    "student_monthly_price_ghs": "50.00",
    "pro_monthly_price_ghs": "350.00",
    "firm_monthly_price_ghs": "800.00",
    "institution_monthly_price_ghs": "3500.00",
    # Yearly prices
    "student_yearly_price_ghs": "500.00",
    "pro_yearly_price_ghs": "3500.00",
    "firm_yearly_price_ghs": "8000.00",
    "institution_yearly_price_ghs": "35000.00",
    # Paystack plan codes (Stage 1.5). Admin pastes these in after creating
    # the matching Plan in the Paystack dashboard. Stored as strings.
    "paystack_plan_student_monthly": "",
    "paystack_plan_student_yearly": "",
    "paystack_plan_pro_monthly": "",
    "paystack_plan_pro_yearly": "",
    "paystack_plan_firm_monthly": "",
    "paystack_plan_firm_yearly": "",
    "paystack_plan_institution_monthly": "",
    "paystack_plan_institution_yearly": "",
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

_INT_CONFIG_KEYS = {
    "free_tier_daily_limit",
    "student_daily_limit",
    "professional_daily_limit",
    "firm_daily_limit",
    "institution_daily_limit",
}

_STR_CONFIG_KEYS = {
    "paystack_plan_student_monthly",
    "paystack_plan_student_yearly",
    "paystack_plan_pro_monthly",
    "paystack_plan_pro_yearly",
    "paystack_plan_firm_monthly",
    "paystack_plan_firm_yearly",
    "paystack_plan_institution_monthly",
    "paystack_plan_institution_yearly",
}


async def get_platform_config() -> dict:
    """Fetch all platform config rows from DB, falling back to defaults.

    Daily limits → int (-1 = unlimited).
    Paystack plan codes → str (empty string when unconfigured).
    Everything else → float (prices in GHS).
    """
    async with get_session() as session:
        result = await session.execute(select(PlatformConfig))
        rows = {row.key: row.value for row in result.scalars().all()}

    merged: dict = {}
    for key, default_fn in _CONFIG_DEFAULTS.items():
        raw = rows.get(key)
        if raw is None:
            raw = default_fn() if callable(default_fn) else default_fn
        if key in _INT_CONFIG_KEYS:
            merged[key] = int(raw)
        elif key in _STR_CONFIG_KEYS:
            merged[key] = str(raw)
        else:
            merged[key] = float(raw)

    return merged


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

# Plan → config-key mapping for daily limits. ENTERPRISE is deprecated but
# kept here so existing accounts continue to be treated as unlimited.
_PLAN_DAILY_LIMIT_KEY = {
    PlanType.FREE: "free_tier_daily_limit",
    PlanType.STUDENT: "student_daily_limit",
    PlanType.PROFESSIONAL: "professional_daily_limit",
    PlanType.FIRM: "firm_daily_limit",
    PlanType.INSTITUTION: "institution_daily_limit",
    PlanType.ENTERPRISE: "institution_daily_limit",
}

# Tolerance for legitimate price drift between the moment the customer pays
# and the moment we verify. 1 GHS is well below the smallest meaningful
# pricing change.
_AMOUNT_TOLERANCE_GHS = 1.0


def _plan_from_metadata(metadata: dict | None) -> PlanType | None:
    """Map frontend-attached metadata {plan: 'firm', cycle: 'monthly'} → PlanType.

    This is the *most reliable* signal because the frontend explicitly tells us
    which tier the customer chose. Paystack returns the metadata blob in both
    the verify-payment response and the webhook events.
    """
    if not isinstance(metadata, dict):
        return None
    plan_str = (metadata.get("plan") or "").strip().lower()
    if not plan_str:
        return None
    try:
        return PlanType(plan_str)
    except ValueError:
        return None


def _plan_from_paystack_code(plan_code: str, cfg: dict) -> PlanType | None:
    """Map a Paystack plan_code (from subscription events) → PlanType.

    Matches the code against the 8 admin-configured paystack_plan_* slots in
    PlatformConfig. Empty/unconfigured slots are skipped.
    """
    if not plan_code:
        return None
    code_to_plan = {
        cfg.get("paystack_plan_student_monthly"): PlanType.STUDENT,
        cfg.get("paystack_plan_student_yearly"): PlanType.STUDENT,
        cfg.get("paystack_plan_pro_monthly"): PlanType.PROFESSIONAL,
        cfg.get("paystack_plan_pro_yearly"): PlanType.PROFESSIONAL,
        cfg.get("paystack_plan_firm_monthly"): PlanType.FIRM,
        cfg.get("paystack_plan_firm_yearly"): PlanType.FIRM,
        cfg.get("paystack_plan_institution_monthly"): PlanType.INSTITUTION,
        cfg.get("paystack_plan_institution_yearly"): PlanType.INSTITUTION,
    }
    # Drop empty/missing codes so the dict can't collide on empty-string keys.
    code_to_plan = {k: v for k, v in code_to_plan.items() if k}
    return code_to_plan.get(plan_code)


def _plan_from_amount(amount_ghs: float, cfg: dict) -> PlanType | None:
    """Defensive fallback: match the paid amount against configured tier prices.

    Useful when neither metadata nor plan_code is present (e.g. legacy webhook
    payloads, manual transfers). Amount collisions exist (pro_yearly and
    institution_monthly are both GHS 3,500 by default), so this is LAST resort.
    """
    candidates = [
        (cfg.get("student_monthly_price_ghs"), PlanType.STUDENT),
        (cfg.get("student_yearly_price_ghs"), PlanType.STUDENT),
        (cfg.get("pro_monthly_price_ghs"), PlanType.PROFESSIONAL),
        (cfg.get("pro_yearly_price_ghs"), PlanType.PROFESSIONAL),
        (cfg.get("firm_monthly_price_ghs"), PlanType.FIRM),
        (cfg.get("firm_yearly_price_ghs"), PlanType.FIRM),
        (cfg.get("institution_monthly_price_ghs"), PlanType.INSTITUTION),
        (cfg.get("institution_yearly_price_ghs"), PlanType.INSTITUTION),
    ]
    for price, plan in candidates:
        if price is None:
            continue
        if abs(amount_ghs - float(price)) <= _AMOUNT_TOLERANCE_GHS:
            return plan
    return None


async def resolve_plan_from_payment(
    *,
    metadata: dict | None = None,
    plan_code: str | None = None,
    amount_ghs: float | None = None,
) -> tuple[PlanType | None, str]:
    """Identify which PlanType a Paystack payment corresponds to.

    Priority order:
      1. `metadata.plan` — frontend told us explicitly. Most trustworthy.
      2. `plan_code` — Paystack subscription event names the plan directly.
      3. `amount_ghs` — last-resort price matching with tolerance.

    Returns (plan, source). `source` ∈ {"metadata", "plan_code", "amount",
    "unresolved"}. When unresolved, the caller MUST refuse to silently
    upgrade — log loudly and require admin intervention instead.
    """
    if metadata:
        plan = _plan_from_metadata(metadata)
        if plan is not None:
            return plan, "metadata"

    cfg = await get_platform_config()

    if plan_code:
        plan = _plan_from_paystack_code(plan_code, cfg)
        if plan is not None:
            return plan, "plan_code"

    if amount_ghs is not None:
        plan = _plan_from_amount(float(amount_ghs), cfg)
        if plan is not None:
            return plan, "amount"

    return None, "unresolved"


async def price_for_plan(plan: PlanType, cycle: str | None = None) -> float:
    """Return the configured GHS price for a tier × billing-cycle.

    `cycle` ∈ {"monthly", "yearly"}. Defaults to "monthly" when omitted.
    FREE returns 0. Deprecated ENTERPRISE returns its legacy monthly price.
    """
    if plan == PlanType.FREE:
        return 0.0
    cfg = await get_platform_config()
    cycle_norm = (cycle or "monthly").strip().lower()
    is_yearly = cycle_norm in ("yearly", "annual", "annually", "year")
    key_map = {
        PlanType.STUDENT: ("student_yearly_price_ghs" if is_yearly else "student_monthly_price_ghs"),
        PlanType.PROFESSIONAL: ("pro_yearly_price_ghs" if is_yearly else "pro_monthly_price_ghs"),
        PlanType.FIRM: ("firm_yearly_price_ghs" if is_yearly else "firm_monthly_price_ghs"),
        PlanType.INSTITUTION: ("institution_yearly_price_ghs" if is_yearly else "institution_monthly_price_ghs"),
        # ENTERPRISE is dormant — historic rows fall through to the default below.
    }
    key = key_map.get(plan, "institution_monthly_price_ghs")
    return float(cfg.get(key, 0.0))


def _daily_limit_for(plan: PlanType, cfg: dict) -> int:
    """Resolve a plan's daily query limit from platform config. -1 = unlimited."""
    key = _PLAN_DAILY_LIMIT_KEY.get(plan, "free_tier_daily_limit")
    return int(cfg.get(key, 0))


async def check_quota(clerk_id: str) -> dict:
    """Check if a user can make another query.

    Each tier has its own daily limit configured in PlatformConfig.
    A limit of -1 means unlimited.

    Returns:
        dict with keys:
            - allowed (bool): Whether the query is permitted
            - remaining (int): Queries remaining today (-1 for unlimited)
            - plan (str): Current plan name
            - daily_limit (int): The daily limit for the user's plan (-1 for unlimited)
            - used_today (int): Queries used today
    """
    await get_or_create_user(clerk_id)

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        user = result.scalar_one_or_none()

        cfg = await get_platform_config()
        daily_limit = _daily_limit_for(user.plan, cfg)

        # Unlimited tier — no need to count.
        if daily_limit < 0:
            return {
                "allowed": True,
                "remaining": -1,
                "plan": user.plan.value,
                "daily_limit": -1,
                "used_today": 0,
            }

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


async def update_user_plan_by_clerk_id(
    clerk_id: str,
    plan: PlanType,
    paystack_subscription_code: str | None = None,
    paystack_customer_code: str | None = None,
) -> User | None:
    """Update a user's plan by their Clerk ID.

    Preferred over email lookup since the Clerk ID is the stable user
    identifier — email-based lookups fail when users were auto-provisioned
    with placeholder addresses before they paid.
    """
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            logger.warning(f"Plan update: no user found for clerk_id {clerk_id}")
            return None

        old_plan = user.plan
        user.plan = plan
        user.updated_at = datetime.now(timezone.utc)

        if paystack_subscription_code:
            sub_result = await session.execute(
                select(Subscription).where(
                    Subscription.paystack_subscription_code == paystack_subscription_code
                )
            )
            subscription = sub_result.scalar_one_or_none()
            if subscription is None:
                session.add(Subscription(
                    clerk_id=user.clerk_id,
                    paystack_subscription_code=paystack_subscription_code,
                    paystack_customer_code=paystack_customer_code,
                    plan=plan,
                    status=SubscriptionStatus.ACTIVE,
                    started_at=datetime.now(timezone.utc),
                ))
            else:
                subscription.plan = plan
                subscription.status = (
                    SubscriptionStatus.ACTIVE
                    if plan != PlanType.FREE
                    else SubscriptionStatus.CANCELLED
                )
        elif paystack_customer_code:
            # No subscription code (one-off charge), but we can still link
            # the customer code to the most recent subscription row.
            sub_result = await session.execute(
                select(Subscription)
                .where(Subscription.clerk_id == user.clerk_id)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            subscription = sub_result.scalar_one_or_none()
            if subscription and not subscription.paystack_customer_code:
                subscription.paystack_customer_code = paystack_customer_code

        logger.info(
            f"User plan updated by clerk_id: {user.email} | {old_plan.value} → {plan.value}"
        )
        return user


async def record_payment(
    *,
    reference: str,
    clerk_id: str | None,
    email: str | None,
    amount_ghs: float,
    currency: str,
    status: str,
    plan: PlanType,
    paystack_customer_code: str | None = None,
    channel: str | None = None,
    source: str = "verify_endpoint",
    paid_at: datetime | None = None,
    raw_response: dict | None = None,
) -> Payment:
    """Persist a Paystack payment record for the admin audit trail.

    Idempotent on ``reference`` — re-calling with the same reference updates
    the existing row rather than creating a duplicate. The verify endpoint
    and webhook can therefore both write the same payment safely.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Payment).where(Payment.reference == reference)
        )
        payment = result.scalar_one_or_none()

        if payment is None:
            payment = Payment(
                reference=reference,
                clerk_id=clerk_id,
                email=email,
                amount_ghs=amount_ghs,
                currency=currency,
                status=status,
                plan=plan,
                paystack_customer_code=paystack_customer_code,
                channel=channel,
                source=source,
                paid_at=paid_at,
                raw_response=raw_response,
            )
            session.add(payment)
            logger.info(f"Payment recorded: ref={reference} clerk_id={clerk_id} amount=GHS {amount_ghs}")
        else:
            # Backfill fields that may have been missing on the prior write
            payment.clerk_id = payment.clerk_id or clerk_id
            payment.email = payment.email or email
            payment.status = status
            payment.paystack_customer_code = payment.paystack_customer_code or paystack_customer_code
            payment.channel = payment.channel or channel
            payment.paid_at = payment.paid_at or paid_at
            if raw_response is not None:
                payment.raw_response = raw_response
            logger.debug(f"Payment record updated: ref={reference}")

        return payment


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
        # Today's usage count per user.
        usage_today_sub = (
            select(UsageLog.clerk_id, sql_func.count(UsageLog.id).label("used_today"))
            .where(UsageLog.created_at >= today_start)
            .group_by(UsageLog.clerk_id)
            .subquery()
        )

        # Lifetime usage count per user (no date filter).
        usage_total_sub = (
            select(UsageLog.clerk_id, sql_func.count(UsageLog.id).label("total_queries"))
            .group_by(UsageLog.clerk_id)
            .subquery()
        )

        query = (
            select(
                User,
                sql_func.coalesce(usage_today_sub.c.used_today, 0).label("used_today"),
                sql_func.coalesce(usage_total_sub.c.total_queries, 0).label("total_queries"),
            )
            .outerjoin(usage_today_sub, User.clerk_id == usage_today_sub.c.clerk_id)
            .outerjoin(usage_total_sub, User.clerk_id == usage_total_sub.c.clerk_id)
        )

        if search:
            query = query.where(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.clerk_id.ilike(f"%{search}%"),
                )
            )

        count_q = select(sql_func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        rows = (await session.execute(query)).all()

    users_out = [
        {
            "clerk_id": row.User.clerk_id,
            "email": row.User.email,
            "plan": row.User.plan.value,
            "used_today": row.used_today,
            "total_queries": row.total_queries,
            "created_at": row.User.created_at.isoformat() if row.User.created_at else None,
            "updated_at": row.User.updated_at.isoformat() if row.User.updated_at else None,
        }
        for row in rows
    ]

    return {"users": users_out, "total": total, "page": page, "per_page": per_page}
