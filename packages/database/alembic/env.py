"""Alembic environment configuration."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini (config) file in use
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from infalette_database.base import Base
from infalette_database.models import *  # noqa: F401, F403

target_metadata = Base.metadata

# Reuse the asyncpg sslmode->ssl translation from the runtime session
# module so the same DSN works for both the API and migrations.
from infalette_database.session import _build_engine_kwargs  # noqa: E402


def get_engine_kwargs() -> dict:
    """Return kwargs for ``create_async_engine`` that handle asyncpg SSL.

    SQLAlchemy's asyncpg dialect forwards the libpq-style ``sslmode``
    query param straight to ``asyncpg.connect()``, which only accepts
    ``ssl`` (bool/SSLContext). We strip ``sslmode`` from the DSN and
    pass ``ssl=True`` via connect_args when the URL targets Neon.
    """
    from infalette_config import get_settings

    return _build_engine_kwargs(get_settings().database.migration_url())


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_engine_kwargs()["url"]
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy.ext.asyncio import create_async_engine

    kwargs = get_engine_kwargs()
    connectable = create_async_engine(
        kwargs.pop("url"),
        poolclass=pool.NullPool,
        **kwargs,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
