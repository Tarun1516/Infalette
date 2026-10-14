"""Database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infalette_config import get_settings


def _normalize_dsn_for_asyncpg(url: str) -> str:
    """Translate libpq-style SSL params into what asyncpg actually accepts.

    asyncpg does not understand ``sslmode=require`` (a libpq-ism). When
    the DSN carries any ``sslmode`` value, swap it for ``ssl=true`` so
    SQLAlchemy's asyncpg dialect can forward it correctly. Any other
    query params are kept as-is.
    """
    parts = urlsplit(url)
    if not parts.query:
        return url
    params = parse_qs(parts.query, keep_blank_values=True)
    if "sslmode" not in params:
        return url
    # sslmode=disable -> no SSL. Everything else (require, verify-ca,
    # verify-full, prefer, allow) -> SSL on. asyncpg defaults to a
    # permissive SSL context which is fine for Neon.
    mode = (params.pop("sslmode") or [""])[0].lower()
    params["ssl"] = ["false" if mode == "disable" else "true"]
    new_query = urlencode([(k, v) for k, vs in params.items() for v in vs])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def _build_engine_kwargs(url: str) -> dict:
    """Return kwargs (url, connect_args) for ``create_async_engine``.

    SQLAlchemy's asyncpg dialect auto-extracts ``sslmode`` from the DSN
    and forwards it as-is to ``asyncpg.connect()``, which only accepts
    ``ssl`` (bool/SSLContext). We strip ``sslmode`` from the URL and
    pass ``ssl=True`` via connect_args when the URL targets a TLS-only
    host (Neon, any cloud Postgres with ``sslmode=require``).
    """
    from sqlalchemy.engine.url import make_url

    parsed = make_url(url)
    connect_args: dict = {}
    if parsed.drivername.startswith("postgresql+asyncpg") or parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+asyncpg")
        q = dict(parsed.query)
        if "sslmode" in q:
            raw = q.pop("sslmode")
            mode = raw.lower() if isinstance(raw, str) else ""
            if mode != "disable":
                connect_args["ssl"] = True
        parsed = parsed.set(query=q)
    return {"url": parsed, "connect_args": connect_args}


def _create_engine():
    """Create async engine from settings.

    Uses ``DatabaseSettings.resolved_url()`` so that Neon deployments
    transparently pick up ``DATABASE_URL_POOLED`` while local dev (and any
    caller still setting only ``DATABASE_URL``) keeps working.
    """
    settings = get_settings()
    kwargs = _build_engine_kwargs(settings.database.resolved_url())
    return create_async_engine(
        kwargs["url"],
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        echo=settings.debug,
        connect_args=kwargs["connect_args"],
    )


_engine = None
_session_factory = None


def get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting an async database session.

    Pins ``app.current_tenant_id`` on the connection when the request
    context carries a tenant (set by AuthMiddleware), activating the
    row-level-security policies from migration 006. Uses session-scoped
    set_config so it survives mid-request commits, and resets it on exit
    so pooled connections never leak tenant context. Entirely best-effort:
    sqlite/test/CLI paths without a tenant simply skip the GUC.
    """
    from sqlalchemy import text

    from infalette_database.context import current_tenant_id

    session_factory = get_session_factory()
    async with session_factory() as session:
        tid = current_tenant_id.get()
        if tid:
            try:
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tid, false)"),
                    {"tid": str(tid)},
                )
            except Exception:
                pass  # sqlite/tests/GUC unavailable — RLS stays default-open

        try:
            yield session
        finally:
            if tid:
                try:
                    await session.execute(
                        text(
                            "SELECT set_config('app.current_tenant_id', '', false)"
                        )
                    )
                except Exception:
                    pass


async def init_db() -> None:
    """Initialize database (create tables if needed).

    Wrapped in a short retry loop to absorb Neon's autosuspend cold-start:
    when the compute has gone to sleep, the first connection attempt can take
    1-5s to wake and may surface as a ``ConnectionDoesNotExistError``,
    ``OperationalError``, or ``PoolTimeout``. Five attempts with exponential
    backoff (1s, 2s, 4s, 8s, 16s, capped at 30s) covers the worst observed
    wake window. The final attempt is re-raised so caller-facing errors
    remain unchanged.
    """
    import asyncio
    import logging

    from infalette_database.base import Base
    from sqlalchemy.exc import OperationalError

    logger = logging.getLogger(__name__)
    engine = get_engine()
    max_attempts = 5
    base_delay = 1.0
    cap_delay = 30.0

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            if attempt > 1:
                logger.info("init_db succeeded on attempt %d", attempt)
            return
        except (OperationalError, OSError) as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = min(cap_delay, base_delay * (2 ** (attempt - 1)))
            logger.warning(
                "init_db attempt %d/%d failed (%s); retrying in %.1fs",
                attempt, max_attempts, exc.__class__.__name__, delay,
            )
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc
