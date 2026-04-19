"""PostgreSQL async database engine for Ghana Legal AI SaaS.

Provides connection pooling, session management, and table lifecycle
using SQLAlchemy 2.0 async engine with asyncpg driver.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ghana_legal.config import settings

# Module-level engine (initialized lazily)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async SQLAlchemy engine (singleton).

    Uses asyncpg driver with connection pooling configured for
    production workloads (min 2, max 10 connections).
    """
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL is not configured. "
                "Set it in your .env file, e.g.: "
                "DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ghana_legal"
            )
        # Supavisor transaction pooler compatibility specifically for asyncpg
        db_url = settings.DATABASE_URL
        if "pooler.supabase.com" in db_url and ":5432" in db_url:
            db_url = db_url.replace(":5432", ":6543")

        _engine = create_async_engine(
            db_url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False,
            connect_args={
                "server_settings": {"application_name": "ghana_legal_modal"},
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            }
        )
        logger.info("PostgreSQL async engine created")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory (singleton)."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager that yields a database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize the database: create all tables if they don't exist.

    Called during FastAPI startup lifecycle.
    """
    from ghana_legal.domain.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables initialized successfully")


async def close_db() -> None:
    """Close the database connection pool.

    Called during FastAPI shutdown lifecycle.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("PostgreSQL connection pool closed")
