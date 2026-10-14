"""Notification sending task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.customer import Customer
from infalette_integrations.email.client import EmailClient

logger = logging.getLogger(__name__)


async def send_notification(
    session: AsyncSession,
    tenant_id: UUID,
    notification_type: str,
    recipient_id: UUID = None,
    email: str = None,
    subject: str = None,
    message: str = None,
) -> dict:
    """Send a notification."""
    email_client = EmailClient()

    # Resolve recipient
    to_email = email
    if not to_email and recipient_id:
        result = await session.execute(
            select(Customer).where(Customer.id == recipient_id)
        )
        customer = result.scalar_one_or_none()
        if customer:
            to_email = customer.email

    if not to_email:
        return {"status": "error", "error": "No recipient email"}

    # Send notification
    await email_client.send_email(
        to=to_email,
        subject=subject or f"Notification: {notification_type}",
        html_content=message or f"You have a new {notification_type} notification.",
        tenant_id=tenant_id,
    )

    return {
        "status": "sent",
        "type": notification_type,
        "recipient": to_email,
        "sent_at": datetime.utcnow().isoformat(),
    }


async def send_bulk_notifications(
    session: AsyncSession,
    tenant_id: UUID,
    notification_type: str,
    subject: str,
    message: str,
    segment: str = None,
) -> dict:
    """Send bulk notifications to a customer segment."""
    query = select(Customer).where(Customer.tenant_id == tenant_id)
    if segment:
        query = query.where(Customer.tags.contains([segment]))

    result = await session.execute(query)
    customers = list(result.scalars().all())

    email_client = EmailClient()
    sent = 0
    errors = 0

    for customer in customers:
        if not customer.email:
            continue
        try:
            await email_client.send_email(
                to=customer.email,
                subject=subject,
                html_content=message,
                tenant_id=tenant_id,
            )
            sent += 1
        except Exception as e:
            logger.error(f"Error sending notification to {customer.email}: {e}")
            errors += 1

    return {
        "sent": sent,
        "errors": errors,
        "total": len(customers),
    }


@shared_task(name="apps.workers.tasks.notifications.send_notification")
def send_notification_task(
    tenant_id: str = None,
    customer_id: str = None,
    to: str = None,
    subject: str = "",
    html_content: str = "",
    notification_type: str = "generic",
) -> dict:
    """Celery entry point: send one transactional notification email."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            cid = UUID(customer_id) if customer_id else None
            tid = UUID(tenant_id) if tenant_id else None
            if tid is None and cid:
                result = await session.execute(
                    select(Customer.tenant_id).where(Customer.id == cid)
                )
                row = result.first()
                tid = row[0] if row else None
            return await send_notification(
                session,
                tenant_id=tid,
                notification_type=notification_type,
                recipient_id=cid,
                email=to,
                subject=subject,
                message=html_content,
            )

    return asyncio.run(_run())


@shared_task(name="apps.workers.tasks.notifications.send_bulk_notifications")
def send_bulk_notifications_task(
    tenant_id: str = "",
    tag: str = None,
    subject: str = "",
    html_content: str = "",
) -> dict:
    """Celery entry point: blast a tagged customer segment."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            return await send_bulk_notifications(
                session,
                tenant_id=UUID(tenant_id),
                notification_type="broadcast",
                subject=subject,
                message=html_content,
                segment=tag,
            )

    return asyncio.run(_run())
