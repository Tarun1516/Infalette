"""Social media posting task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.order import Order
from infalette_database.models.product import Product
from infalette_integrations.email.client import EmailClient

logger = logging.getLogger(__name__)


async def post_to_social(
    session: AsyncSession,
    tenant_id: UUID,
    platform: str,
    message: str,
    image_url: str = None,
) -> dict:
    """Announce content to a tenant's audience channels.

    Instagram does not allow arbitrary feed posting without content-
    publishing permissions and an attached media container, so the
    reliable delivery path is: persist a `social.posted` event (CRM
    timeline + analytics) and fan the message out to every active
    tenant webhook endpoint, signed with each endpoint's secret.
    """
    import hashlib
    import hmac as hmac_mod
    import json

    import httpx

    from infalette_analytics.event_bus import record_event

    payload = {
        "type": "social.post",
        "platform": platform,
        "message": message,
        "image_url": image_url,
        "posted_at": datetime.utcnow().isoformat(),
    }
    body = json.dumps(payload).encode()

    delivered = 0
    failed = 0
    # Webhook fan-out uses registered outbound endpoints
    from infalette_database.models.webhook_endpoint import WebhookEndpoint

    endpoints = list(
        (
            await session.execute(
                select(WebhookEndpoint).where(
                    WebhookEndpoint.tenant_id == tenant_id,
                    WebhookEndpoint.status == "active",
                )
            )
        ).scalars()
    )
    for endpoint in endpoints:
        if not endpoint.url:
            continue
        headers = {"Content-Type": "application/json"}
        if endpoint.secret:
            headers["X-Infalette-Signature"] = hmac_mod.new(
                str(endpoint.secret).encode(), body, hashlib.sha256
            ).hexdigest()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(endpoint.url, content=body, headers=headers, timeout=10)
            if resp.status_code in (200, 201, 202):
                delivered += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning("Social post webhook to %s failed: %s", endpoint.url, e)
            failed += 1

    try:
        await record_event(
            tenant_id=tenant_id,
            actor_id=None,
            event_type="social.posted",
            payload={"platform": platform, "message": message, **payload},
            session=session,
        )
    except Exception:
        pass

    return {
        "status": "posted" if delivered or not endpoints else "no_endpoints",
        "platform": platform,
        "message": message,
        "delivered_to": delivered,
        "failed": failed,
        "posted_at": payload["posted_at"],
    }


async def post_new_order_notification(
    session: AsyncSession,
    tenant_id: UUID,
    order_id: UUID,
    platforms: list[str] = None,
) -> dict:
    """Post a new order notification to social media."""
    result = await session.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return {"status": "error", "error": "Order not found"}

    message = f"New order received! Order #{order.id} for {order.total_cents / 100} {order.currency}"

    results = []
    for platform in platforms or ["instagram"]:
        result = await post_to_social(session, tenant_id, platform, message)
        results.append(result)

    return {
        "order_id": str(order_id),
        "posts": results,
    }


async def post_product_launch(
    session: AsyncSession,
    tenant_id: UUID,
    product_id: UUID,
    platforms: list[str] = None,
) -> dict:
    """Post a product launch notification to social media."""
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return {"status": "error", "error": "Product not found"}

    message = f"New product launched: {product.name}! {product.description[:100]}..."

    results = []
    for platform in platforms or ["instagram"]:
        result = await post_to_social(
            session, tenant_id, platform, message, product.image_url
        )
        results.append(result)

    return {
        "product_id": str(product_id),
        "posts": results,
    }


@shared_task(name="apps.workers.tasks.social.post_to_social")
def post_to_social_task(platform: str, message: str, tenant_id: str = None) -> dict:
    """Celery entry point: post a message to a social platform."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            tid = UUID(tenant_id) if tenant_id else None
            return await post_to_social(session, tenant_id=tid, platform=platform, message=message)

    return asyncio.run(_run())
