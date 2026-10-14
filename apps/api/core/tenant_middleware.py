"""Tenant resolution middleware."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from infalette_auth.tenant import TenantResolver


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware for resolving tenant context from domain or JWT."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._tenant_resolver = TenantResolver()

    async def dispatch(self, request: Request, call_next):
        """Resolve tenant context and attach to request state."""
        tenant_context = await self._tenant_resolver.get_tenant_context(request)
        request.state.tenant_context = tenant_context
        return await call_next(request)
