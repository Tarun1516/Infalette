"""Tenant management services."""

from __future__ import annotations

import socket
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.tenant import Tenant, TenantStatus
from infalette_database.models.domain import Domain
from infalette_database.models.user import User
from infalette_database.models.role import Role, UserRole
from infalette_auth.security import PasswordHasher
from infalette_validation.schemas import TenantCreate


async def create_tenant(data: TenantCreate, session: AsyncSession) -> Tenant:
    """Create a new tenant with admin user.

    Args:
        data: Tenant creation data.
        session: Database session.

    Returns:
        The created tenant.
    """
    # Create tenant
    slug = data.name.lower().replace(" ", "-").replace("_", "-")
    tenant = Tenant(
        name=data.name,
        slug=slug,
        plan_id=data.plan_id,
        status=TenantStatus.ACTIVE,
    )
    session.add(tenant)
    await session.flush()

    # Spec §4 event model: tenant.created
    try:
        from infalette_analytics.event_bus import record_event

        await record_event(
            tenant_id=tenant.id,
            actor_id=None,
            event_type="tenant.created",
            payload={"tenant_id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
            session=session,
        )
    except Exception:
        pass

    # Create admin user
    hasher = PasswordHasher()
    password_hash = hasher.hash_password(data.admin_password)

    # Get or create tenant_owner role
    admin_user = User(
        tenant_id=tenant.id,
        email=data.admin_email,
        password_hash=password_hash,
        first_name="Admin",
        last_name="User",
        role=UserRole.TENANT_OWNER.value,
        status="active",
    )
    session.add(admin_user)
    await session.flush()

    # Create default domain
    domain = Domain(
        tenant_id=tenant.id,
        domain=f"{slug}.infalette.com",
        is_primary=True,
        verified=True,
    )
    session.add(domain)

    await session.commit()
    await session.refresh(tenant)
    return tenant


async def get_tenant(tenant_id: UUID, session: AsyncSession) -> Tenant | None:
    """Get a tenant by ID.

    Args:
        tenant_id: The tenant ID.
        session: Database session.

    Returns:
        The tenant if found, None otherwise.
    """
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def list_tenants(session: AsyncSession) -> list[Tenant]:
    """List all tenants.

    Args:
        session: Database session.

    Returns:
        List of all tenants.
    """
    result = await session.execute(select(Tenant))
    return list(result.scalars().all())


async def update_tenant(tenant_id: UUID, data: TenantCreate, session: AsyncSession) -> Tenant | None:
    """Update a tenant.

    Args:
        tenant_id: The tenant ID.
        data: Updated tenant data.
        session: Database session.

    Returns:
        The updated tenant if found, None otherwise.
    """
    result = await session.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id)
        .values(name=data.name, plan_id=data.plan_id)
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_tenant(tenant_id, session)


async def delete_tenant(tenant_id: UUID, session: AsyncSession) -> None:
    """Delete a tenant.

    Args:
        tenant_id: The tenant ID.
        session: Database session.
    """
    await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
    await session.commit()


async def assign_plan(tenant_id: UUID, plan_id: UUID, session: AsyncSession) -> Tenant | None:
    """Assign a plan to a tenant.

    Args:
        tenant_id: The tenant ID.
        plan_id: The plan ID.
        session: Database session.

    Returns:
        The updated tenant if found, None otherwise.
    """
    await session.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id)
        .values(plan_id=plan_id)
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_tenant(tenant_id, session)


async def list_domains(tenant_id: UUID, session: AsyncSession) -> list[Domain]:
    """List domains for a tenant.

    Args:
        tenant_id: The tenant ID.
        session: Database session.

    Returns:
        List of domains owned by the tenant.
    """
    result = await session.execute(
        select(Domain).where(Domain.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def create_domain(
    tenant_id: UUID,
    domain: str,
    is_primary: bool,
    session: AsyncSession,
) -> Domain:
    """Create a domain for a tenant.

    Args:
        tenant_id: The tenant ID.
        domain: The domain hostname.
        is_primary: Whether the domain is the tenant's primary domain.
        session: Database session.

    Returns:
        The created Domain (verified=False until DNS verification succeeds).
    """
    record = Domain(
        tenant_id=tenant_id,
        domain=domain,
        is_primary=is_primary,
        verified=False,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def verify_domain(tenant_id: UUID, domain_id: UUID, session: AsyncSession) -> dict | None:
    """Verify a tenant's custom domain via DNS resolution.

    Loads the Domain scoped by id+tenant_id (route maps None to 404),
    resolves it using stdlib socket.getaddrinfo inside try/except,
    sets verified=True on success / False on failure, commits, and
    returns a result dict recording the verification method.

    Returns:
        {"domain": ..., "verified": bool, "resolved": bool, ...} or
        None when the domain does not exist for this tenant.
    """
    result = await session.execute(
        select(Domain).where(Domain.id == domain_id, Domain.tenant_id == tenant_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    method = "socket.getaddrinfo"
    resolved_ips: list[str] = []
    error: str | None = None
    try:
        infos = socket.getaddrinfo(record.domain, None)
        # Deduplicate resolved addresses; empty set means nothing resolvable.
        resolved_ips = sorted({info[4][0] for info in infos})
    except OSError as exc:
        error = str(exc)

    resolved = len(resolved_ips) > 0
    record.verified = resolved

    # Auto-promote to primary when the tenant has no primary domain yet
    promoted_to_primary = False
    if resolved and not record.is_primary:
        existing_primary = await session.execute(
            select(Domain).where(
                Domain.tenant_id == tenant_id,
                Domain.is_primary == True,  # noqa: E712
                Domain.id != record.id,
            )
        )
        if existing_primary.scalar_one_or_none() is None:
            record.is_primary = True
            promoted_to_primary = True

    await session.commit()

    return {
        "domain": record.domain,
        "verified": record.verified,
        "resolved": resolved,
        "is_primary": record.is_primary,
        "promoted_to_primary": promoted_to_primary,
        "method": method,
        "resolved_ips": resolved_ips,
        "error": error,
        "checked_at": datetime.utcnow().isoformat(),
    }
