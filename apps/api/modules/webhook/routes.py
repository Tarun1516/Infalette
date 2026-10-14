"""Webhook management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def list_webhook_endpoints(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List webhook endpoints for the tenant."""
    from apps.api.modules.webhook.services import list_webhook_endpoints
    return await list_webhook_endpoints(user.tenant_id, session)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_webhook_endpoint(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new webhook endpoint."""
    from apps.api.modules.webhook.services import create_webhook_endpoint
    return await create_webhook_endpoint(user.tenant_id, data, session)


@router.get("/{endpoint_id}")
async def get_webhook_endpoint(
    endpoint_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a webhook endpoint by ID."""
    from apps.api.modules.webhook.services import get_webhook_endpoint
    endpoint = await get_webhook_endpoint(user.tenant_id, endpoint_id, session)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return endpoint


@router.patch("/{endpoint_id}")
async def update_webhook_endpoint(
    endpoint_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a webhook endpoint."""
    from apps.api.modules.webhook.services import update_webhook_endpoint
    return await update_webhook_endpoint(user.tenant_id, endpoint_id, data, session)


@router.delete("/{endpoint_id}")
async def delete_webhook_endpoint(
    endpoint_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a webhook endpoint."""
    from apps.api.modules.webhook.services import delete_webhook_endpoint
    await delete_webhook_endpoint(user.tenant_id, endpoint_id, session)
    return {"message": "Webhook endpoint deleted"}


@router.get("/{endpoint_id}/deliveries")
async def get_webhook_deliveries(
    endpoint_id: UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get webhook deliveries for an endpoint."""
    from apps.api.modules.webhook.services import get_webhook_deliveries
    return await get_webhook_deliveries(user.tenant_id, endpoint_id, session, limit)


@router.post("/{endpoint_id}/test")
async def send_test_webhook(
    endpoint_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Send a test webhook to an endpoint."""
    from apps.api.modules.webhook.services import send_test_webhook
    return await send_test_webhook(user.tenant_id, endpoint_id, session)
