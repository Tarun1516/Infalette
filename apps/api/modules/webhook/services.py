"""Webhook management services."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import Request, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.webhook_endpoint import WebhookEndpoint
from infalette_database.models.webhook_delivery import WebhookDelivery
from infalette_analytics.event_bus import record_event


async def list_webhook_endpoints(
    tenant_id: UUID,
    session: AsyncSession,
) -> list[WebhookEndpoint]:
    """List webhook endpoints for a tenant."""
    result = await session.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def get_webhook_endpoint(
    tenant_id: UUID,
    endpoint_id: UUID,
    session: AsyncSession,
) -> WebhookEndpoint | None:
    """Get a webhook endpoint by ID."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_webhook_endpoint(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> WebhookEndpoint:
    """Create a new webhook endpoint."""
    endpoint = WebhookEndpoint(
        tenant_id=tenant_id,
        name=data.get("name") or "Unnamed endpoint",
        url=data.get("url"),
        events=data.get("events", []),
        secret=data.get("secret"),
        status=data.get("status", "active"),
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def update_webhook_endpoint(
    tenant_id: UUID,
    endpoint_id: UUID,
    data: dict,
    session: AsyncSession,
) -> WebhookEndpoint | None:
    """Update a webhook endpoint."""
    endpoint = await get_webhook_endpoint(tenant_id, endpoint_id, session)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    for key, value in data.items():
        if hasattr(endpoint, key) and value is not None:
            setattr(endpoint, key, value)

    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def delete_webhook_endpoint(
    tenant_id: UUID,
    endpoint_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete a webhook endpoint."""
    await session.execute(
        delete(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def get_webhook_deliveries(
    tenant_id: UUID,
    endpoint_id: UUID,
    session: AsyncSession,
    limit: int = 100,
) -> list[WebhookDelivery]:
    """Get webhook deliveries for an endpoint."""
    result = await session.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == endpoint_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def send_test_webhook(
    tenant_id: UUID,
    endpoint_id: UUID,
    session: AsyncSession,
) -> dict:
    """Send a test webhook to an endpoint."""
    endpoint = await get_webhook_endpoint(tenant_id, endpoint_id, session)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    import httpx
    import json
    import hmac
    import hashlib

    payload = {"test": True, "timestamp": datetime.utcnow().isoformat()}
    body = json.dumps(payload).encode()

    headers = {"Content-Type": "application/json"}
    if endpoint.secret:
        signature = hmac.new(
            endpoint.secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Infalette-Signature"] = signature

    status_code: int | None = None
    error_message: str | None = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint.url, content=body, headers=headers, timeout=10)
            status_code = response.status_code
            success = response.status_code in (200, 201, 202)
    except Exception as e:
        success = False
        error_message = str(e)

    delivery = WebhookDelivery(
        endpoint_id=endpoint_id,
        event_type="test",
        payload_json=payload,
        status="success" if success else "failed",
        response_status=status_code,
        response_code=status_code,
        error=error_message,
    )
    session.add(delivery)
    await session.commit()

    return {
        "endpoint_id": str(endpoint_id),
        "success": success,
        "status_code": status_code,
    }


async def process_webhook_event(
    request: Request,
    provider: str,
    session: AsyncSession,
) -> dict:
    """Process an incoming webhook event from a provider."""
    body = await request.body()
    payload = {}

    try:
        import json
        payload = json.loads(body)
    except Exception:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # Record the event
    await record_event(
        tenant_id=None,
        actor_id=None,
        event_type=f"webhook.{provider}",
        payload=payload,
        session=session,
    )

    return {"status": "received", "provider": provider}
