"""Request-scoped database context.

``current_tenant_id`` is a ContextVar set by AuthMiddleware once the tenant
is resolved (JWT/domain/subdomain). ``get_async_session`` reads it and pins
the Postgres GUC ``app.current_tenant_id`` on the connection so that the
row-level-security policies installed by alembic migration 006 enforce
tenant isolation at the database layer.

Contract:
- Unset/empty GUC  -> policies are DEFAULT-OPEN (COALESCE fallback) so tests,
  workers and CLI scripts are unaffected.
- Set GUC          -> queries are restricted to that tenant_id at the DB level,
  independent of application-layer filters.
"""

from __future__ import annotations

from contextvars import ContextVar

# str(uuid) or None
current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id", default=None
)

PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000000"
