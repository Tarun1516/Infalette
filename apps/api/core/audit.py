"""Audit logging utility and middleware.

Logs POST/PATCH/DELETE/PUT mutations to audit_logs with tenant scoping.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Paths to exclude from audit (health, docs, etc.)
AUDIT_EXCLUDE_PREFIXES = ("/health", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi", "/webhooks")


async def log_audit(
    tenant_id: Optional[UUID],
    actor_id: Optional[UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[UUID],
    payload: Optional[dict],
    ip_address: Optional[str],
    session,
) -> None:
    """Persist an audit log entry; never raises."""
    try:
        from infalette_database.models.audit_log import AuditLog

        entry = AuditLog(
            tenant_id=tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_json=payload or {},
            ip_address=ip_address,
        )
        session.add(entry)
        await session.commit()
    except Exception as e:
        logger.warning("audit log failed: %s", e)


def _infer_resource(request: Request) -> tuple[str, Optional[UUID]]:
    """Infer resource_type and resource_id from path."""
    path = request.url.path
    # Strip prefix /api/v1/
    parts = [p for p in path.split("/") if p]
    # e.g. ["api","v1","leads","{id}"] or ["api","v1","stores","{id}","pages"]
    # Find first segment after api/v1
    try:
        api_idx = parts.index("v1")
        rest = parts[api_idx + 1 :]
    except ValueError:
        rest = parts
    if not rest:
        return "unknown", None
    resource_type = rest[0].rstrip("s")  # crude singularize: leads -> lead
    # singular mapping
    mapping = {
        "lead": "lead",
        "customer": "customer",
        "order": "order",
        "cart": "cart",
        "store": "store",
        "product": "product",
        "checkout": "checkout",
        "auth": "auth",
        "analytics": "analytics",
    }
    resource_type = mapping.get(resource_type, resource_type)
    resource_id = None
    if len(rest) > 1:
        try:
            resource_id = UUID(rest[1])
        except Exception:
            resource_id = None
    return resource_type, resource_id


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs mutating requests to audit_logs."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Only audit mutating methods
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        # Exclude health/docs/webhooks
        if any(request.url.path.startswith(p) for p in AUDIT_EXCLUDE_PREFIXES):
            return await call_next(request)

        # Capture response first
        response = await call_next(request)

        # Only audit 2xx-3xx to avoid noise
        if not (200 <= response.status_code < 400):
            return response

        # Try to log audit asynchronously without blocking failure
        try:
            # Lazy import session maker to avoid circular deps
            from infalette_database.session import get_async_session  # type: ignore
            # We cannot easily get session here without request dependency;
            # Instead we open a new session via async context if available
            # Try to use request.state for tenant/actor if AuthMiddleware already ran
            tenant_id = None
            actor_id = None
            tc = getattr(request.state, "tenant_context", None)
            if tc and hasattr(tc, "tenant_id"):
                tenant_id = getattr(tc, "tenant_id", None)
            # Try to get user from Authorization header fallback
            # We avoid DB query here; if we can get user via request.state
            user = getattr(request.state, "user", None)
            if user and hasattr(user, "id"):
                actor_id = user.id
                if not tenant_id and hasattr(user, "tenant_id"):
                    tenant_id = user.tenant_id

            # Infer resource
            resource_type, resource_id = _infer_resource(request)
            action = request.method.lower()  # post/put/patch/delete

            # Attempt to get DB session via dependency – we create one manually
            # This is best-effort; if DB not configured, skip
            try:
                from infalette_database.session import async_session_factory  # type: ignore
                async with async_session_factory() as session:  # type: ignore
                    await log_audit(
                        tenant_id=tenant_id,
                        actor_id=actor_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        payload={"path": request.url.path, "method": request.method},
                        ip_address=request.client.host if request.client else None,
                        session=session,
                    )
            except Exception as inner:
                # Fallback: try get_async_session generator
                logger.debug("audit session fallback failed: %s", inner)
        except Exception as e:
            logger.debug("audit middleware error: %s", e)

        return response
