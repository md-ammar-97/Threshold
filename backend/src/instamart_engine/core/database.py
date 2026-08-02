"""Async SQLAlchemy engine, session factory, and declarative base.

All domain models import `Base` from here so Alembic's autogenerate can see
every table through a single metadata object.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from instamart_engine.core.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for every domain model in this package."""


class UUIDPrimaryKeyMixin:
    """Every primary entity uses a database-generated UUID primary key.

    See datamodel.md §2.6 / §3.2 — source-native IDs are external identifiers
    only, never primary keys.
    """

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )


class TimestampMixin:
    """Standard `created_at`/`updated_at` columns per datamodel.md §3.3."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a request-scoped session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def check_database_connection() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - health check must not raise
        return False
