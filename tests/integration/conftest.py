"""Test configuration for integration tests."""

import pytest
import asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

try:
    from infalette_database.models import Base
except ImportError:
    from infalette_database.base import Base


TEST_DATABASE_URL = "postgresql+asyncpg://infalette:infalette@localhost:5432/infalette_test"
SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///:memory:"


try:
    import pytest_asyncio
    _async_fixture = pytest_asyncio.fixture
except ImportError:
    _async_fixture = pytest.fixture  # fallback

@_async_fixture
async def db_session():
    """Create a test database session.

    Tries PostgreSQL first; falls back to SQLite in-memory if PostgreSQL unavailable (e.g., CI without Postgres).
    """
    # Try PostgreSQL
    engine = None
    fallback = False
    try:
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        # Try to create tables – will fail if DB unreachable
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # Fallback to SQLite
        if engine is not None:
            try:
                await engine.dispose()
            except Exception:
                pass
        fallback = True
        engine = create_async_engine(SQLITE_FALLBACK_URL, echo=False, connect_args={"check_same_thread": False})
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    try:
        async with async_session() as session:
            yield session
    finally:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        except Exception:
            pass
        await engine.dispose()


@pytest.fixture
def tenant_id():
    """Generate a test tenant ID."""
    return uuid4()


@pytest.fixture
def customer_id():
    """Generate a test customer ID."""
    return uuid4()


@pytest.fixture
def product_id():
    """Generate a test product ID."""
    return uuid4()
