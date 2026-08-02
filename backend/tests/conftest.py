"""Shared test fixtures.

`db_session` gives integration tests a real AsyncSession backed by the live
Postgres (docker-compose's `postgres` service / Settings.DATABASE_URL), but
every change is rolled back at the end of the test via the standard
SQLAlchemy "join session to an external transaction" pattern — even though
the code under test calls `session.commit()` internally, only the SAVEPOINT
commits; the outer transaction is always rolled back.

https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites

The fixture creates and disposes its own engine per test rather than reusing
`core.database.get_engine()`'s cached singleton: pytest-asyncio gives each
test function its own event loop by default, and asyncpg connections can't
be reused across event loops (doing so crashes on Windows' ProactorEventLoop
during pool cleanup).
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from instamart_engine.core.config import get_settings


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().DATABASE_URL)
    connection = await engine.connect()
    outer_transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await outer_transaction.rollback()
        await connection.close()
        await engine.dispose()
