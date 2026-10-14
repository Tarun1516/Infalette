"""Expired-checkout inventory release task.

Checkouts reserve stock at creation and expire after 2h
(Checkout.expires_at). This beat job cancels expired PENDING checkouts
and returns their reserved units to stock — without it, abandoned
checkouts permanently shrink sellable inventory.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def release_expired_checkouts(
    session,
    tenant_id: UUID | None = None,
    batch: int = 200,
) -> dict:
    """Cancel expired pending checkouts and restock their items."""
    from infalette_database.models.checkout import Checkout, CheckoutStatus
    from infalette_database.models.checkout_item import CheckoutItem
    from infalette_commerce.inventory import release_inventory

    now = datetime.utcnow()
    query = (
        select(Checkout)
        .where(
            Checkout.status == CheckoutStatus.PENDING,
            Checkout.expires_at.isnot(None),
            Checkout.expires_at < now,
        )
        .limit(batch)
    )
    if tenant_id:
        query = query.where(Checkout.tenant_id == tenant_id)

    checkouts = list((await session.execute(query)).scalars().all())
    released_checkouts = 0
    released_units = 0

    for checkout in checkouts:
        items = list(
            (
                await session.execute(
                    select(CheckoutItem).where(CheckoutItem.checkout_id == checkout.id)
                )
            ).scalars().all()
        )
        for item in items:
            await release_inventory(
                item.product_id, item.quantity, session, variant_id=item.variant_id
            )
            released_units += item.quantity

        checkout.status = CheckoutStatus.CANCELLED
        released_checkouts += 1

    if released_checkouts:
        await session.commit()

        # Emit events so analytics/CRM see the releases (best-effort)
        try:
            from infalette_analytics.event_bus import record_event

            for checkout in checkouts:
                await record_event(
                    tenant_id=checkout.tenant_id,
                    actor_id=None,
                    event_type="checkout.expired",
                    payload={
                        "checkout_id": str(checkout.id),
                        "total_cents": checkout.total_cents,
                    },
                    session=session,
                )
        except Exception as exc:
            logger.debug("checkout.expired event emission skipped: %s", exc)

    return {
        "expired_checkouts_found": len(checkouts),
        "released_checkouts": released_checkouts,
        "released_units": released_units,
    }


@shared_task(name="apps.workers.tasks.checkout_expiry.release_expired_checkout_inventory")
def release_expired_inventory_task(tenant_id: str | None = None) -> dict:
    """Celery entry point."""

    async def _run() -> dict:
        from infalette_database.session import get_session_factory

        async with get_session_factory()() as session:
            return await release_expired_checkouts(
                session,
                tenant_id=UUID(tenant_id) if tenant_id else None,
            )

    try:
        result = asyncio.run(_run())
        logger.info("release_expired_inventory: %s", result)
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("release_expired_inventory failed: %s", exc, exc_info=True)
        return {"error": str(exc)}
