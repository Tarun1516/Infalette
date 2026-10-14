"""Analytics management services."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.event import Event
from infalette_database.models.order import Order
from infalette_database.models.customer import Customer
from infalette_database.models.lead import Lead
from infalette_analytics.event_bus import record_event
from infalette_analytics.aggregator import AnalyticsAggregator


async def get_dashboard_metrics(
    tenant_id: UUID,
    session: AsyncSession,
    days: int = 30,
) -> dict:
    """Get dashboard metrics for a tenant."""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Total orders
    result = await session.execute(
        select(func.count()).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= start_date,
        )
    )
    total_orders = result.scalar() or 0

    # Total revenue
    result = await session.execute(
        select(func.sum(Order.total_cents)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= start_date,
        )
    )
    total_revenue = result.scalar() or 0

    # Total customers
    result = await session.execute(
        select(func.count()).where(
            Customer.tenant_id == tenant_id,
            Customer.created_at >= start_date,
        )
    )
    total_customers = result.scalar() or 0

    # Total leads
    result = await session.execute(
        select(func.count()).where(
            Lead.tenant_id == tenant_id,
            Lead.created_at >= start_date,
        )
    )
    total_leads = result.scalar() or 0

    return {
        "total_orders": total_orders,
        "total_revenue_cents": total_revenue,
        "total_customers": total_customers,
        "total_leads": total_leads,
        "period_days": days,
    }


async def get_sales_analytics(
    tenant_id: UUID,
    session: AsyncSession,
    days: int = 30,
) -> list[dict]:
    """Get sales analytics over time."""
    start_date = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(
            func.date(Order.created_at).label("date"),
            func.count().label("orders"),
            func.sum(Order.total_cents).label("revenue"),
        )
        .where(
            Order.tenant_id == tenant_id,
            Order.created_at >= start_date,
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )

    return [
        {"date": row.date, "orders": row.orders, "revenue_cents": row.revenue or 0}
        for row in result.fetchall()
    ]


async def get_top_products(
    tenant_id: UUID,
    session: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """Get top selling products."""
    from infalette_database.models.order_item import OrderItem
    from infalette_database.models.product import Product

    result = await session.execute(
        select(
            Product.name,
            func.sum(OrderItem.quantity).label("total_sold"),
            func.sum(OrderItem.price_cents * OrderItem.quantity).label("revenue"),
        )
        .join(OrderItem, Product.id == OrderItem.product_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.tenant_id == tenant_id)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )

    return [
        {"name": row.name, "total_sold": row.total_sold, "revenue_cents": row.revenue or 0}
        for row in result.fetchall()
    ]


async def get_customer_analytics(
    tenant_id: UUID,
    session: AsyncSession,
) -> dict:
    """Get customer analytics."""
    result = await session.execute(
        select(
            func.count().label("total_customers"),
            func.avg(func.count(Order.id)).label("avg_orders_per_customer"),
        )
        .outerjoin(Order, Customer.id == Order.customer_id)
        .where(Customer.tenant_id == tenant_id)
        .group_by(Customer.id)
    )

    customers = result.fetchall()
    total_customers = len(customers)

    return {
        "total_customers": total_customers,
        "avg_orders_per_customer": sum(c.avg_orders_per_customer or 0 for c in customers) / max(total_customers, 1),
    }


async def get_conversion_funnel(
    tenant_id: UUID,
    session: AsyncSession,
    days: int = 30,
) -> dict:
    """Get conversion funnel data."""
    aggregator = AnalyticsAggregator()
    return await aggregator.get_funnel(tenant_id, session, days)


async def get_event_analytics(
    tenant_id: UUID,
    session: AsyncSession,
    event_type: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """Get event analytics."""
    start_date = datetime.utcnow() - timedelta(days=days)

    query = select(
        Event.event_type,
        func.count().label("count"),
    ).where(
        Event.tenant_id == tenant_id,
        Event.created_at >= start_date,
    )

    if event_type:
        query = query.where(Event.event_type == event_type)

    query = query.group_by(Event.event_type).order_by(func.count().desc())

    result = await session.execute(query)

    return [
        {"event_type": row.event_type, "count": row.count}
        for row in result.fetchall()
    ]


async def get_abandoned_segments(
    tenant_id: UUID,
    session: AsyncSession,
    hours: int = 24,
    limit: int = 50,
) -> dict:
    """Abandoned-cart and abandoned-social-checkout segments (spec §2 CRM).

    - Abandoned carts: carts with items untouched for `hours` hours.
    - Abandoned social checkouts: leads whose conversation produced a
      checkout.created event but no payment.succeeded within the window.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import select, func
    from infalette_database.models.cart import Cart
    from infalette_database.models.cart_item import CartItem
    from infalette_database.models.customer import Customer
    from infalette_database.models.event import Event
    from infalette_database.models.lead import Lead

    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # --- Abandoned carts ---
    result = await session.execute(
        select(Cart)
        .outerjoin(CartItem, CartItem.cart_id == Cart.id)
        .where(
            Cart.tenant_id == tenant_id,
            Cart.updated_at < cutoff,
        )
        .group_by(Cart.id)
        .having(func.count(CartItem.id) > 0)
        .limit(limit)
    )
    carts = list(result.scalars())

    # Resolve customer emails for recovery
    customer_ids = {c.customer_id for c in carts if c.customer_id}
    customers = {}
    if customer_ids:
        rows = await session.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )
        customers = {c.id: c for c in rows.scalars()}

    abandoned_carts = []
    for cart in carts:
        customer = customers.get(cart.customer_id)
        abandoned_carts.append({
            "cart_id": str(cart.id),
            "customer_id": str(cart.customer_id) if cart.customer_id else None,
            "email": customer.email if customer else None,
            "session_key": cart.session_key,
            "total_cents": cart.total_cents,
            "updated_at": cart.updated_at.isoformat() if cart.updated_at else None,
        })

    # --- Abandoned social checkouts: leads with checkout but no paid order ---
    result = await session.execute(
        select(Event.payload_json)
        .where(
            Event.tenant_id == tenant_id,
            Event.event_type == "checkout.created",
            Event.created_at >= cutoff,
        )
        .limit(limit * 2)
    )
    checkout_payloads = [row[0] or {} for row in result.fetchall()]

    # Collect direct lead_id links AND resolve social session hints
    # (``lead:{email}`` from wa-/ig- generated checkouts). Only genuine
    # UUIDs may enter lead_ids_with_checkout — hints are emails resolved
    # through the synthetic channel-email convention.
    import re as _re
    import uuid as _uuid

    _hint_re = _re.compile(r"^lead:(.+@.+)$")

    lead_ids_with_checkout: list[str] = []
    hint_emails: list[str] = []  # channel-convention emails
    for payload in checkout_payloads:
        lid = payload.get("lead_id")
        hint = payload.get("lead_hint") or ""
        try:
            if lid and str(_uuid.UUID(str(lid))) == str(lid):
                if str(lid) not in {str(x) for x in lead_ids_with_checkout}:
                    lead_ids_with_checkout.append(str(lid))
                continue
        except (ValueError, TypeError, AttributeError):
            pass
        m = _hint_re.match(str(lid or hint))
        if m and m.group(1) not in hint_emails:
            hint_emails.append(m.group(1))

    # Resolve hinted emails to real leads (social checkouts carry the
    # synthetic channel email convention).
    if hint_emails:
        rows = await session.execute(
            select(Lead).where(
                Lead.tenant_id == tenant_id,
                Lead.email.in_(hint_emails),
            )
        )
        for l in rows.scalars():
            if str(l.id) not in {str(x) for x in lead_ids_with_checkout}:
                lead_ids_with_checkout.append(str(l.id))

    abandoned_social = []
    if lead_ids_with_checkout:
        rows = await session.execute(
            select(Lead).where(
                Lead.tenant_id == tenant_id,
                Lead.id.in_([lid for lid in lead_ids_with_checkout]),
            )
        )
        leads_by_id = {str(l.id): l for l in rows.scalars()}
        paid_events = (
            await session.execute(
                select(Event.payload_json).where(
                    Event.tenant_id == tenant_id,
                    Event.event_type == "payment.succeeded",
                    Event.created_at >= cutoff,
                )
            )
        ).fetchall()
        paid_lead_ids = {
            (row[0] or {}).get("lead_id") for row in paid_events
        }

        for lid in lead_ids_with_checkout:
            if lid in paid_lead_ids:
                continue  # converted — not abandoned
            lead = leads_by_id.get(lid)
            if lead:
                abandoned_social.append({
                    "lead_id": str(lead.id),
                    "email": lead.email,
                    "first_name": lead.first_name,
                    "stage": str(getattr(lead.stage, "value", lead.stage)),
                    "source": lead.source,
                })

    return {
        "abandoned_carts": abandoned_carts,
        "abandoned_social_checkouts": abandoned_social,
        "window_hours": hours,
    }


async def get_channel_attribution(
    tenant_id: UUID,
    session: AsyncSession,
    days: int = 30,
) -> dict:
    """Channel attribution from checkout.created event sources."""
    from infalette_analytics.dashboard import DashboardService

    service = DashboardService()
    return await service.get_channel_attribution(tenant_id, session, days)
