"""Tenant context resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Request

from infalette_database.models.tenant import Tenant
from infalette_database.models.domain import Domain
from infalette_auth.jwt import TokenManager


@dataclass
class TenantContext:
    """Tenant context resolved from domain or JWT."""

    tenant_id: UUID
    tenant: Optional[Tenant] = None
    domain: Optional[str] = None
    is_platform: bool = False


class TenantResolver:
    """Resolves tenant from domain, subdomain, or JWT token."""

    def __init__(self) -> None:
        self._token_manager = TokenManager()

    async def resolve_tenant_from_domain(self, domain: str) -> Optional[Tenant]:
        """Resolve tenant from custom domain.

        Args:
            domain: The domain to resolve.

        Returns:
            The tenant if found, None otherwise.
        """
        from sqlalchemy import select
        from infalette_database.session import get_session_factory
        from infalette_database.models.domain import Domain

        async with get_session_factory()() as session:
            result = await session.execute(
                select(Domain).where(Domain.domain == domain)
            )
            domain_record = result.scalar_one_or_none()
            if domain_record:
                result = await session.execute(
                    select(Tenant).where(Tenant.id == domain_record.tenant_id)
                )
                return result.scalar_one_or_none()
        return None

    async def resolve_tenant_from_subdomain(self, subdomain: str) -> Optional[Tenant]:
        """Resolve tenant from subdomain.

        Args:
            subdomain: The subdomain to resolve.

        Returns:
            The tenant if found, None otherwise.
        """
        from sqlalchemy import select
        from infalette_database.session import get_session_factory

        async with get_session_factory()() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.slug == subdomain)
            )
            return result.scalar_one_or_none()

    async def get_tenant_context(self, request: Request) -> TenantContext:
        """Get tenant context from request.

        Resolution order:
        1. JWT token (for authenticated requests)
        2. Custom domain
        3. Subdomain

        Args:
            request: The FastAPI request.

        Returns:
            The tenant context.
        """
        # Try JWT token first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = self._token_manager.decode_token(token)
                return TenantContext(
                    tenant_id=UUID(payload.tenant_id),
                    is_platform=payload.sub == "platform",
                )
            except Exception:
                pass

        # Try domain resolution
        host = request.headers.get("Host", "")
        if host:
            tenant = await self.resolve_tenant_from_domain(host)
            if tenant:
                return TenantContext(
                    tenant_id=tenant.id,
                    tenant=tenant,
                    domain=host,
                )

            # Try subdomain
            subdomain = host.split(".")[0] if "." in host else host
            tenant = await self.resolve_tenant_from_subdomain(subdomain)
            if tenant:
                return TenantContext(
                    tenant_id=tenant.id,
                    tenant=tenant,
                    domain=host,
                )

        # Platform admin
        return TenantContext(
            tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
            is_platform=True,
        )
