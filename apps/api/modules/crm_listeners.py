"""Event-driven lead stage progression (spec §3 CRM pipeline).

Subscribes to domain events on the global event bus and advances the
linked lead's stage:

  checkout.created  -> checkout_created
  payment.succeeded / order.cod_created -> paid
  order.fulfilled   -> fulfilled
  repeat purchase (2nd+ paid order for the same customer) -> repeat_customer

Also stamps lead_id/customer_id onto checkout/payment events so the
abandoned-social segment and timelines can join on them.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select

from infalette_database.models.lead import Lead, LeadStage
from infalette_analytics.event_bus import get_event_bus

logger = logging.getLogger(__name__)

_STAGE_ON_EVENT = {
    "checkout.created": LeadStage.CHECKOUT_CREATED,
    "payment.succeeded": LeadStage.PAID,
    "order.cod_created": LeadStage.PAID,
    "order.fulfilled": LeadStage.FULFILLED,
}

_STAGE_ORDER = [
    LeadStage.NEW_LEAD,
    LeadStage.NEW,
    LeadStage.ENGAGED,
    LeadStage.PRODUCT_SELECTED,
    LeadStage.CHECKOUT_CREATED,
    LeadStage.PAID,
    LeadStage.FULFILLED,
    LeadStage.REPEAT_CUSTOMER,
]


async def _advance_lead_stage(lead: Lead, target: LeadStage) -> bool:
    """Move a lead forward only (never regress a later stage)."""
    try:
        current = getattr(lead, "status", None)
        current_idx = (
            _STAGE_ORDER.index(current) if current in _STAGE_ORDER else -1
        )
        target_idx = (
            _STAGE_ORDER.index(target) if target in _STAGE_ORDER else -1
        )
        if target_idx <= current_idx:
            return False
        lead.status = target.value if hasattr(target, "value") else str(target)
        return True
    except Exception as exc:
        logger.debug("stage advance skipped: %s", exc)
        return False


async def handle_stage_progression(event) -> None:
    """Advance lead stages from a domain event.

    The event bus passes the Event row; payload keys ``lead_id`` and
    ``customer_id`` link the event to the lead.
    """
    session_factory = None
    try:
        # Use our own session — the producer's session may already be closed
        from infalette_database.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            payload = getattr(event, "payload_json", None) or {}
            lead_id = payload.get("lead_id")
            customer_id = payload.get("customer_id")
            event_type = getattr(event, "event_type", "")

            target = _STAGE_ON_EVENT.get(event_type)
            if target is None:
                return

            lead = None
            if lead_id:
                lead = (
                    await session.execute(
                        select(Lead).where(
                            Lead.id == UUID(str(lead_id)),
                            Lead.tenant_id == event.tenant_id,
                        )
                    )
                ).scalar_one_or_none()
            elif customer_id:
                lead = (
                    await session.execute(
                        select(Lead).where(
                            Lead.customer_id == UUID(str(customer_id)),
                            Lead.tenant_id == event.tenant_id,
                        )
                    )
                ).scalars().first()

            if lead is None:
                return

            # Web campaign attribution: stamp the lead's campaign from the
            # checkout's resolved utm_campaign (spec §3 campaign attribution).
            if event_type == "checkout.created":
                campaign_id = payload.get("campaign_id")
                if campaign_id and not getattr(lead, "campaign_id", None):
                    try:
                        lead.campaign_id = UUID(str(campaign_id))
                    except (ValueError, AttributeError):
                        pass

            advanced = await _advance_lead_stage(lead, target)

            # Repeat-customer detection: >=2 paid orders for this customer
            if event_type == "payment.succeeded" and lead.customer_id:
                from infalette_database.models.order import Order, OrderStatus

                paid_orders = len(
                    (
                        await session.execute(
                            select(Order.id).where(
                                Order.tenant_id == event.tenant_id,
                                Order.customer_id == lead.customer_id,
                                Order.status.in_([
                                    OrderStatus.CONFIRMED,
                                    OrderStatus.PROCESSING,
                                    OrderStatus.SHIPPED,
                                    OrderStatus.DELIVERED,
                                ]),
                            )
                        )
                    ).scalars().all()
                )
                if paid_orders >= 2:
                    await _advance_lead_stage(lead, LeadStage.REPEAT_CUSTOMER)

            await session.commit()
            if advanced:
                logger.info(
                    "lead %s stage -> %s via %s",
                    lead.id,
                    getattr(target, "value", target),
                    event_type,
                )
    except Exception as exc:
        logger.warning("stage progression failed for %s: %s", getattr(event, "event_type", "?"), exc)


def register_crm_listeners() -> None:
    """Idempotently attach CRM listeners to the global event bus."""
    bus = get_event_bus()
    marker = "_crm_listeners_registered"
    if getattr(bus, marker, False):
        return
    for event_type in (
        "checkout.created",
        "payment.succeeded",
        "order.cod_created",
        "order.fulfilled",
    ):
        bus.subscribe(event_type, handle_stage_progression)
    setattr(bus, marker, True)
