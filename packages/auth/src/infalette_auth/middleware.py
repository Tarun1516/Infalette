"""FastAPI middleware for auth and tenant context."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from infalette_auth.tenant import TenantResolver, TenantContext


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication and tenant context resolution."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._tenant_resolver = TenantResolver()

    async def dispatch(self, request: Request, call_next):
        """Process the request, resolving tenant context."""
        start_time = time.time()

        # Resolve tenant context
        tenant_context = await self._tenant_resolver.get_tenant_context(request)
        request.state.tenant_context = tenant_context

        # Expose tenant to the DB layer for RLS (best-effort; see
        # infalette_database/context.py for the GUC contract).
        try:
            from infalette_database.context import (
                current_tenant_id,
                PLATFORM_TENANT_ID,
            )

            tid = getattr(tenant_context, "tenant_id", None)
            is_platform = getattr(tenant_context, "is_platform", False)
            if (
                tid
                and not is_platform
                and str(tid) != PLATFORM_TENANT_ID
            ):
                current_tenant_id.set(str(tid))
            else:
                current_tenant_id.set(None)
        except Exception:
            pass  # never break requests over RLS context

        # Process the request
        response = await call_next(request)

        # Add processing time header
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        return response


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware for tenant context resolution."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._tenant_resolver = TenantResolver()

    async def dispatch(self, request: Request, call_next):
        """Process the request, resolving tenant context."""
        tenant_context = await self._tenant_resolver.get_tenant_context(request)
        request.state.tenant_context = tenant_context
        return await call_next(request)
