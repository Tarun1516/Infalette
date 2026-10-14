"""Integration management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def list_integrations(
    provider: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List integrations for the tenant."""
    from apps.api.modules.integration.services import list_integrations
    return await list_integrations(user.tenant_id, session, provider)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new integration."""
    from apps.api.modules.integration.services import create_integration
    return await create_integration(user.tenant_id, data, session)



@router.get("/providers/available")
async def get_available_providers(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get list of available integration providers."""
    from apps.api.modules.integration.services import get_available_providers
    return await get_available_providers()

@router.get("/{integration_id}")
async def get_integration(
    integration_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get an integration by ID."""
    from apps.api.modules.integration.services import get_integration
    integration = await get_integration(user.tenant_id, integration_id, session)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.patch("/{integration_id}")
async def update_integration(
    integration_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update an integration."""
    from apps.api.modules.integration.services import update_integration
    return await update_integration(user.tenant_id, integration_id, data, session)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete an integration."""
    from apps.api.modules.integration.services import delete_integration
    await delete_integration(user.tenant_id, integration_id, session)
    return {"message": "Integration deleted"}


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Test an integration connection."""
    from apps.api.modules.integration.services import test_integration
    return await test_integration(user.tenant_id, integration_id, session)
