"""Abandoned cart recovery task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.cart import Cart
from infalette_database.models.cart_item import CartItem
from infalette_database.models.customer import Customer
from infalette_database.models.event import Event
from infalette_integrations.email.client import EmailClient
from infalette_automation.checkout_link import CheckoutLinkGenerator
from infalette_automation.schemas import TriggerEvent
from infalette_analytics.event_bus import record_event

logger = logging.getLogger(__name__)


async def recover_abandoned_carts(
    session: AsyncSession,
    tenant_id: UUID = None,
    hours_threshold: int = 24,
) -> dict:
    """Recover abandoned carts by sending recovery emails."""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_threshold)

    query = select(Cart).where(Cart.updated_at < cutoff_time)
    if tenant_id:
        query = query.where(Cart.tenant_id == tenant_id)

    result = await session.execute(query)
    carts = list(result.scalars().all())

    email_client = EmailClient()
    checkout_generator = CheckoutLinkGenerator()
    recovered = 0
    errors = 0
    skipped_no_consent = 0
    skipped_empty = 0
    skipped_already_recovered = 0

    for cart in carts:
        try:
            # Skip empty carts — nothing to recover.
            item_count_result = await session.execute(
                select(func.count()).where(CartItem.cart_id == cart.id)
            )
            if (item_count_result.scalar() or 0) == 0:
                skipped_empty += 1
                continue

            # Get customer
            result = await session.execute(
                select(Customer).where(Customer.id == cart.customer_id)
            )
            customer = result.scalar_one_or_none()
            if not customer or not customer.email:
                continue

            # Consent gate (spec: follow-up only where consent permits).
            from infalette_commerce.consent import customer_can_contact

            if not customer_can_contact(customer, "email"):
                skipped_no_consent += 1
                continue

            # Suppression: never re-contact a cart we already recovered.
            already = (
                await session.execute(
                    select(Event).where(
                        Event.tenant_id == cart.tenant_id,
                        Event.event_type == "cart.recovery_sent",
                        Event.created_at >= datetime.utcnow() - timedelta(days=7),
                    )
                )
            ).scalars().all()
            already_keys = {
                str((e.payload_json or {}).get("cart_id")) for e in already
            }
            if str(cart.id) in already_keys:
                skipped_already_recovered += 1
                continue

            # Determine last_item_added_at from the cart (fallback to cart update time)
            last_item_added_at = (
                cart.updated_at.isoformat() if getattr(cart, "updated_at", None) else None
            )
            try:
                last_item_row = await session.execute(
                    select(func.max(CartItem.added_at)).where(CartItem.cart_id == cart.id)
                )
                last_item_added = last_item_row.scalar()
                if last_item_added is not None:
                    last_item_added_at = last_item_added.isoformat()
            except Exception:
                pass

            # Persist the cart.abandoned domain event so automation rules
            # and analytics segments can react to it.
            try:
                await record_event(
                    tenant_id=cart.tenant_id,
                    actor_id=cart.customer_id,
                    event_type="cart.abandoned",
                    payload={
                        "cart_id": str(cart.id),
                        "customer_id": str(cart.customer_id),
                        "last_item_added_at": last_item_added_at,
                        "tenant_id": str(cart.tenant_id),
                    },
                    session=session,
                )
            except Exception as exc:
                logger.debug(f"record_event(cart.abandoned) skipped: {exc}")

            # Create checkout link
            event = TriggerEvent(
                event_type="cart.abandoned",
                tenant_id=cart.tenant_id,
                actor_id=cart.customer_id,
                payload={
                    "customer_id": str(cart.customer_id),
                    "cart_id": str(cart.id),
                },
                timestamp=datetime.utcnow(),
            )
            link = await checkout_generator.create_link(event, {}, session)

            # Send recovery email
            await email_client.send_email(
                to=customer.email,
                subject="You left items in your cart!",
                html_content=f"""
                <h2>Hi {customer.first_name or 'there'}!</h2>
                <p>You left some items in your cart. Complete your purchase now:</p>
                <a href="{link}">Complete Your Order</a>
                <p>This link expires in 48 hours.</p>
                """,
                tenant_id=cart.tenant_id,
            )

            # Durable suppression marker (7-day window enforced above).
            try:
                from infalette_analytics.event_bus import record_event

                await record_event(
                    tenant_id=cart.tenant_id,
                    actor_id=cart.customer_id,
                    event_type="cart.recovery_sent",
                    payload={"cart_id": str(cart.id)},
                    session=session,
                )
            except Exception:
                pass

            recovered += 1
        except Exception as e:
            logger.error(f"Error recovering cart {cart.id}: {e}", exc_info=True)
            errors += 1

    return {
        "carts_processed": len(carts),
        "recovered": recovered,
        "skipped_no_consent": skipped_no_consent,
        "skipped_empty": skipped_empty,
        "skipped_already_recovered": skipped_already_recovered,
        "errors": errors,
    }


@shared_task(name="apps.workers.tasks.abandoned.recover_abandoned_carts")
def recover_abandoned_carts_task(tenant_id: str = None, hours_threshold: int = 24) -> dict:
    """Celery entry point: email recovery links for stale carts."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            tid = UUID(tenant_id) if tenant_id else None
            return await recover_abandoned_carts(
                session, tenant_id=tid, hours_threshold=hours_threshold
            )

    return asyncio.run(_run())
