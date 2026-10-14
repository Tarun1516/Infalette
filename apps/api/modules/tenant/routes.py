"""Tenant management routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_database.models.tenant import Tenant
from infalette_database.models.domain import Domain
from infalette_database.models.role import Role, UserRole
from infalette_auth.dependencies import get_current_user, require_role
from infalette_auth.schemas import RegisterRequest
from infalette_validation.schemas import TenantCreate, TenantRead

router = APIRouter()


class DomainCreate(BaseModel):
    """Payload for creating a tenant domain."""

    domain: str = Field(..., min_length=3, max_length=255)
    is_primary: bool = False


async def _ensure_tenant_access(
    tenant_id: UUID,
    user,
    session: AsyncSession,
) -> None:
    """Allow if the user belongs to the tenant or is a platform owner."""
    if user.tenant_id == tenant_id:
        return
    role_value = getattr(user.role, "value", str(user.role or ""))
    if role_value == UserRole.PLATFORM_OWNER.value:
        return
    raise HTTPException(status_code=403, detail="Not authorized for this tenant")


@router.post("/", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role("platform_owner")),
):
    """Create a new tenant (platform owner only)."""
    from apps.api.modules.tenant.services import create_tenant
    return await create_tenant(data, session)


class TenantOnboardRequest(BaseModel):
    """Platform-admin onboarding shape: plan by slug, generated credentials."""

    name: str = Field(..., min_length=1)
    slug: str | None = None
    plan: str | None = "store"
    admin_email: EmailStr | None = None
    admin_password: str | None = Field(default=None, min_length=8)


@router.post("/onboard", status_code=status.HTTP_201_CREATED)
async def onboard_tenant(
    data: TenantOnboardRequest,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role("platform_owner")),
):
    """Create a tenant from a plan *slug* (platform-admin flow).

    Resolves the plan, generates an admin email/password when not
    supplied, creates the tenant + owner user, and opens an active
    subscription.
    """
    import secrets

    from fastapi import HTTPException as _HTTPException
    from sqlalchemy import select as _select

    from apps.api.modules.tenant.services import create_tenant as svc_create_tenant
    from infalette_database.models.plan import Plan

    plan_slug = data.plan or "store"
    plan = (
        await session.execute(_select(Plan).where(Plan.slug == plan_slug))
    ).scalar_one_or_none()
    if plan is None:
        raise _HTTPException(status_code=404, detail=f"Plan '{plan_slug}' not found")

    slug = (data.slug or data.name).lower().replace(" ", "-").replace("_", "-")
    admin_email = data.admin_email or f"owner@{slug}.infalette.com"
    admin_password = data.admin_password or secrets.token_urlsafe(12)

    tenant_create = TenantCreate(
        name=data.name,
        plan_id=plan.id,
        admin_email=admin_email,
        admin_password=admin_password,
    )
    tenant = await svc_create_tenant(tenant_create, session)

    # Open the subscription so /platform/subscriptions reflects it
    try:
        from infalette_database.models.subscription import Subscription
        import datetime as _dt

        sub = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            current_period_start=_dt.datetime.utcnow(),
            current_period_end=_dt.datetime.utcnow() + _dt.timedelta(days=30),
        )
        session.add(sub)
        if hasattr(tenant, "plan"):
            tenant.plan = plan.slug
        await session.commit()
    except Exception:
        pass

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": getattr(tenant.status, "value", tenant.status),
        "plan": plan.slug,
        "admin_email": admin_email,
        "admin_password": admin_password if not data.admin_password else "(as provided)",
    }


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a tenant by ID."""
    await _ensure_tenant_access(tenant_id, user, None)
    from apps.api.modules.tenant.services import get_tenant
    tenant = await get_tenant(tenant_id, session)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/", response_model=list[TenantRead])
async def list_tenants(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role("platform_owner")),
):
    """List all tenants (platform owner only)."""
    from apps.api.modules.tenant.services import list_tenants
    return await list_tenants(session)


@router.put("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: UUID,
    data: TenantCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a tenant."""
    await _ensure_tenant_access(tenant_id, user, None)
    from apps.api.modules.tenant.services import update_tenant
    tenant = await update_tenant(tenant_id, data, session)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role("platform_owner")),
):
    """Delete a tenant (platform owner only)."""
    from apps.api.modules.tenant.services import delete_tenant
    await delete_tenant(tenant_id, session)


@router.get("/{tenant_id}/domains")
async def list_domains(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List domains for a tenant."""
    from apps.api.modules.tenant.services import list_domains
    await _ensure_tenant_access(tenant_id, user, session)
    domains = await list_domains(tenant_id, session)
    return [
        {
            "id": str(d.id),
            "domain": d.domain,
            "is_primary": d.is_primary,
            "verified": d.verified,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in domains
    ]


@router.post("/{tenant_id}/domains", status_code=status.HTTP_201_CREATED)
async def create_domain(
    tenant_id: UUID,
    data: DomainCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a domain for a tenant (unverified until DNS check passes)."""
    from apps.api.modules.tenant.services import create_domain
    await _ensure_tenant_access(tenant_id, user, session)
    record = await create_domain(tenant_id, data.domain, data.is_primary, session)
    return {
        "id": str(record.id),
        "domain": record.domain,
        "is_primary": record.is_primary,
        "verified": record.verified,
    }


@router.post("/{tenant_id}/domains/{domain_id}/verify")
async def verify_domain(
    tenant_id: UUID,
    domain_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Verify a tenant's custom domain by resolving its DNS records."""
    from apps.api.modules.tenant.services import verify_domain
    await _ensure_tenant_access(tenant_id, user, session)
    result = await verify_domain(tenant_id, domain_id, session)
    if not result:
        raise HTTPException(status_code=404, detail="Domain not found")
    return result
