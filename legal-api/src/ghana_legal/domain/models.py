"""SQLAlchemy ORM models for Ghana Legal AI SaaS.

Defines the PostgreSQL schema for user management, subscription tracking,
and per-query usage logging.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class PlanType(str, PyEnum):
    """Subscription plan tiers."""
    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, PyEnum):
    """Paystack subscription states."""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class User(Base):
    """Registered user, linked to Clerk authentication.

    Auto-provisioned on first API request via the Clerk user ID.
    """
    __tablename__ = "users"

    clerk_id = Column(String(255), primary_key=True, comment="Clerk user ID (sub claim)")
    email = Column(String(255), nullable=False, index=True)
    plan = Column(
        Enum(PlanType, name="plan_type", native_enum=False, length=50),
        nullable=False,
        default=PlanType.FREE,
        server_default="free",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    usage_logs = relationship("UsageLog", back_populates="user", lazy="selectin")
    subscriptions = relationship("Subscription", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User clerk_id={self.clerk_id} plan={self.plan}>"


class UsageLog(Base):
    """Per-query audit trail for usage tracking and billing.

    One row per user query. Used to enforce daily free-tier limits.
    """
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clerk_id = Column(
        String(255),
        ForeignKey("users.clerk_id", ondelete="CASCADE"),
        nullable=False,
    )
    query_text = Column(Text, nullable=False)
    expert_id = Column(String(100), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="usage_logs")

    # Index for fast daily count queries: WHERE clerk_id = ? AND created_at >= ?
    __table_args__ = (
        Index("ix_usage_clerk_date", "clerk_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UsageLog id={self.id} clerk_id={self.clerk_id} expert={self.expert_id}>"


class Subscription(Base):
    """Paystack subscription record.

    Tracks the lifecycle of a user's paid subscription (create → active → cancelled).
    """
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clerk_id = Column(
        String(255),
        ForeignKey("users.clerk_id", ondelete="CASCADE"),
        nullable=False,
    )
    paystack_subscription_code = Column(String(255), nullable=True, unique=True)
    paystack_customer_code = Column(String(255), nullable=True)
    plan = Column(
        Enum(PlanType, name="plan_type", native_enum=False, length=50),
        nullable=False,
        default=PlanType.PROFESSIONAL,
    )
    status = Column(
        Enum(SubscriptionStatus, name="subscription_status", native_enum=False, length=50),
        nullable=False,
        default=SubscriptionStatus.PENDING,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} clerk_id={self.clerk_id} plan={self.plan} status={self.status}>"


class PlatformConfig(Base):
    """Live-editable platform configuration (pricing, quotas).

    Stored as key-value rows so admins can update limits and prices
    from the admin dashboard without a code redeploy.

    Canonical keys:
        free_tier_daily_limit      (int)    — daily query cap for free users
        pro_monthly_price_ghs      (float)  — Pro plan price in GHS
        enterprise_monthly_price_ghs (float) — Enterprise plan price in GHS
    """
    __tablename__ = "platform_config"

    key = Column(String(100), primary_key=True, comment="Config key")
    value = Column(String(500), nullable=False, comment="Config value (always stored as string)")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PlatformConfig key={self.key} value={self.value}>"
