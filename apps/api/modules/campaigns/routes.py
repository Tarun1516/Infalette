"""Campaign routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import Feature, require_feature

# Campaign analytics is part of the Advanced sales dashboard (spec §2)
router = APIRouter(dependencies=[Depends(require_feature(Feature.ADVANCED_DASHBOARD))])


@router.get("/")
async def list_campaigns(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List campaigns for the tenant."""
    from apps.api.modules.campaigns.services import list_campaigns
    return await list_campaigns(user.tenant_id, session)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new campaign."""
    from apps.api.modules.campaigns.services import create_campaign
    return await create_campaign(user.tenant_id, data, session)


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a campaign by ID."""
    from apps.api.modules.campaigns.services import get_campaign
    campaign = await get_campaign(user.tenant_id, campaign_id, session)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a campaign."""
    from apps.api.modules.campaigns.services import update_campaign
    return await update_campaign(user.tenant_id, campaign_id, data, session)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a campaign."""
    from apps.api.modules.campaigns.services import delete_campaign
    await delete_campaign(user.tenant_id, campaign_id, session)


@router.get("/{campaign_id}/performance")
async def get_campaign_performance(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get lead and revenue performance for a campaign."""
    from apps.api.modules.campaigns.services import get_campaign_performance
    return await get_campaign_performance(user.tenant_id, campaign_id, session)
