"""Campaign management services."""

from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import cast, func, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.campaign import Campaign, CampaignStatus
from infalette_database.models.lead import Lead
from infalette_database.models.order import Order


def _slugify(name: str) -> str:
    """Convert a campaign name into a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "campaign"


async def list_campaigns(tenant_id: UUID, session: AsyncSession) -> list[Campaign]:
    """List campaigns for a tenant."""
    result = await session.execute(
        select(Campaign).where(Campaign.tenant_id == tenant_id).order_by(Campaign.created_at.desc())
    )
    return list(result.scalars().all())


async def get_campaign(tenant_id: UUID, campaign_id: UUID, session: AsyncSession) -> Campaign | None:
    """Get a campaign by ID, scoped to the tenant."""
    result = await session.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_campaign(tenant_id: UUID, data: dict, session: AsyncSession) -> Campaign:
    """Create a new campaign; slugify name when slug is missing."""
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    status = data.get("status") or CampaignStatus.ACTIVE.value
    try:
        status = CampaignStatus(status).value
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")

    campaign = Campaign(
        tenant_id=tenant_id,
        name=name,
        slug=data.get("slug") or _slugify(name),
        source=data.get("source"),
        utm_source=data.get("utm_source"),
        utm_medium=data.get("utm_medium"),
        utm_campaign=data.get("utm_campaign"),
        status=status,
        starts_at=data.get("starts_at"),
        ends_at=data.get("ends_at"),
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def update_campaign(
    tenant_id: UUID,
    campaign_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Campaign | None:
    """Update a campaign (partial)."""
    campaign = await get_campaign(tenant_id, campaign_id, session)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    allowed = {"name", "slug", "source", "utm_source", "utm_medium", "utm_campaign", "status", "starts_at", "ends_at"}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "status" and value is not None:
            try:
                value = CampaignStatus(value).value
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid status: {value}")
        setattr(campaign, key, value)

    # Keep slug consistent when renaming without an explicit slug
    if not data.get("slug"):
        campaign.slug = _slugify(campaign.name)

    await session.commit()
    await session.refresh(campaign)
    return campaign


async def delete_campaign(tenant_id: UUID, campaign_id: UUID, session: AsyncSession) -> None:
    """Delete a campaign."""
    campaign = await get_campaign(tenant_id, campaign_id, session)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await session.delete(campaign)
    await session.commit()


async def get_campaign_performance(
    tenant_id: UUID,
    campaign_id: UUID,
    session: AsyncSession,
) -> dict:
    """Aggregate lead + revenue performance for one campaign.

    Grouping note: Lead.status is a hybrid_property whose SQL expression
    (`@status.expression`) maps to the plain string column `leads.status`
    (`_status`), so grouping by Lead.status works directly at the SQL level.
    """
    campaign = await get_campaign(tenant_id, campaign_id, session)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Leads per stage: group the leads.status string column.
    stage_rows = await session.execute(
        select(Lead.status, func.count())
        .where(Lead.tenant_id == tenant_id, Lead.campaign_id == campaign_id)
        .group_by(Lead.status)
    )
    leads_by_stage = {stage or "unknown": count for stage, count in stage_rows.all()}
    total_leads = sum(leads_by_stage.values())

    # Customers reached by this campaign
    customer_rows = await session.execute(
        select(Lead.customer_id).where(
            Lead.tenant_id == tenant_id,
            Lead.campaign_id == campaign_id,
            Lead.customer_id.isnot(None),
        )
    )
    customer_ids = [cid for (cid,) in customer_rows.all()]

    attributed_orders = 0
    attributed_revenue_cents = 0
    paid_or_fulfilled_orders = 0
    if customer_ids:
        order_agg = await session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_cents), 0)).where(
                Order.tenant_id == tenant_id,
                Order.customer_id.in_(customer_ids),
            )
        )
        attributed_orders, attributed_revenue_cents = order_agg.one()

        # Count converted (paid/fulfilled) orders. Order.status is a native
        # SAEnum which may store member names or values depending on dialect
        # defaults; lower-cast comparison normalizes both ("PAID"/"paid").
        status_str = func.lower(cast(Order.status, String))
        converted_agg = await session.execute(
            select(func.count(Order.id)).where(
                Order.tenant_id == tenant_id,
                Order.customer_id.in_(customer_ids),
                status_str.in_(("paid", "fulfilled", "delivered")),
            )
        )
        paid_or_fulfilled_orders = converted_agg.scalar() or 0

    conversion_rate = (
        round((paid_or_fulfilled_orders / total_leads) * 100, 2) if total_leads > 0 else 0.0
    )

    return {
        "campaign_id": str(campaign_id),
        "name": campaign.name,
        "leads_by_stage": leads_by_stage,
        "total_leads": total_leads,
        "customers_attributed": len(customer_ids),
        "attributed_orders": attributed_orders,
        "attributed_revenue_cents": attributed_revenue_cents,
        "paid_or_fulfilled_orders": paid_or_fulfilled_orders,
        "conversion_rate": conversion_rate,
    }
