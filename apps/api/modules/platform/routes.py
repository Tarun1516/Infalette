"""Platform-owner billing surfaces: plan catalog and tenant subscriptions.

The subscriptions table records which plan each tenant is on and its
lifecycle. Platform-admin reads both; subscription create resolves plan
slugs. Access requires an authenticated platform-owner token.
"""

from __future__ import annotations

import datetime
from datetime import datetime as dt
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


def _require_platform(user) -> None:
    """Only platform owners manage billing surfaces."""
    role_value = str(getattr(user, "role", "") or "")
    if hasattr(user.role, "value"):
        role_value = user.role.value
    tenant_id = getattr(user, "tenant_id", None)
    from infalette_database.context import PLATFORM_TENANT_ID

    is_platform_tenant = tenant_id is not None and str(tenant_id) == PLATFORM_TENANT_ID
    if role_value.lower() not in ("platform_owner", "admin") and not is_platform_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform owner access required",
        )


@router.get("/plans")
async def list_plans(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Plan catalog (slug, pricing, feature matrix)."""
    from infalette_database.models.plan import Plan

    result = await session.execute(select(Plan).order_by(Plan.price_cents))
    plans = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "plan_type": getattr(p.plan_type, "value", p.plan_type),
            "price_cents": p.price_cents,
            "currency": p.currency,
            "interval": p.interval,
            "features_json": p.features_json or {},
        }
        for p in plans
    ]


@router.get("/subscriptions")
async def list_subscriptions(
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """All tenant subscriptions with their plan (platform owner only)."""
    _require_platform(user)
    from infalette_database.models.subscription import Subscription

    query = select(Subscription).order_by(Subscription.created_at.desc())
    if status_filter:
        query = query.where(Subscription.status == status_filter)
    result = await session.execute(query)
    return [
        {
            "id": str(s.id),
            "tenant_id": str(s.tenant_id),
            "plan_id": str(s.plan_id) if s.plan_id else None,
            "status": s.status,
            "current_period_start": s.current_period_start.isoformat()
            if s.current_period_start
            else None,
            "current_period_end": s.current_period_end.isoformat()
            if s.current_period_end
            else None,
            "cancelled_at": s.cancelled_at.isoformat() if s.cancelled_at else None,
        }
        for s in result.scalars().all()
    ]


class SubscriptionCreate(BaseModel):
    """Assign a plan to a tenant."""

    tenant_id: UUID
    plan_slug: str = Field(..., min_length=1)
    trial_days: int = Field(default=0, ge=0, le=90)


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    data: SubscriptionCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Put a tenant on a plan (creating or renewing its subscription)."""
    _require_platform(user)
    from infalette_database.models.plan import Plan
    from infalette_database.models.tenant import Tenant
    from infalette_database.models.subscription import Subscription

    plan_result = await session.execute(select(Plan).where(Plan.slug == data.plan_slug))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{data.plan_slug}' not found")

    tenant_result = await session.execute(select(Tenant).where(Tenant.id == data.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    now = dt.utcnow()
    end = now + datetime.timedelta(days=30 + data.trial_days)

    existing = (
        await session.execute(
            select(Subscription).where(Subscription.tenant_id == data.tenant_id)
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.plan_id = plan.id
        existing.status = "trialing" if data.trial_days else "active"
        existing.current_period_start = now
        existing.current_period_end = end
        existing.cancelled_at = None
        sub = existing
    else:
        sub = Subscription(
            tenant_id=data.tenant_id,
            plan_id=plan.id,
            status="trialing" if data.trial_days else "active",
            current_period_start=now,
            current_period_end=end,
        )
        session.add(sub)

    # Keep the tenant's denormalized plan slug in sync with the subscription
    try:
        tenant.plan = plan.slug
    except Exception:
        pass

    await session.commit()
    await session.refresh(sub)

    return {
        "id": str(sub.id),
        "tenant_id": str(data.tenant_id),
        "plan_id": str(plan.id),
        "plan_slug": plan.slug,
        "status": sub.status,
        "current_period_end": sub.current_period_end.isoformat()
        if sub.current_period_end
        else None,
    }


@router.delete("/subscriptions/{subscription_id}")
async def cancel_subscription(
    subscription_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Cancel a subscription immediately."""
    _require_platform(user)
    from infalette_database.models.subscription import Subscription

    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.status = "canceled"
    sub.cancelled_at = dt.utcnow()
    await session.commit()

    return {"id": str(sub.id), "status": sub.status}
