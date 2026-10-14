"""Conversion funnel analytics."""

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
from infalette_database.models.checkout import Checkout


class FunnelAnalyzer:
    """Analyzes conversion funnels for a tenant."""

    # Website purchase funnel: each stage maps to the domain event types
    # actually recorded by the platform (commerce/cart services).
    FUNNEL_STAGES = [
        "product_viewed",
        "add_to_cart",
        "checkout_created",
        "payment_succeeded",
        "order_created",
    ]

    STAGE_EVENT_TYPES = {
        "product_viewed": ["product.viewed"],
        "add_to_cart": ["cart.item_added"],
        "checkout_created": ["checkout.created"],
        # COD orders confirm without an online payment success event
        "payment_succeeded": ["payment.succeeded", "order.cod_created"],
        "order_created": ["order.created", "order.cod_created"],
    }

    # Social funnel per spec §3: Comment/DM -> Reply -> Product viewed ->
    # Checkout created -> Payment started -> Paid
    SOCIAL_FUNNEL_STAGES = [
        "comment_or_dm_received",
        "reply_sent",
        "product_viewed",
        "checkout_created",
        "payment_started",
        "paid",
    ]

    async def get_funnel(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Get the conversion funnel for a tenant."""
        start_date = datetime.utcnow() - timedelta(days=days)

        funnel_data = {}
        for stage in self.FUNNEL_STAGES:
            event_types = self.STAGE_EVENT_TYPES.get(stage, [stage])
            result = await session.execute(
                select(func.count()).where(
                    Event.tenant_id == tenant_id,
                    Event.event_type.in_(event_types),
                    Event.created_at >= start_date,
                )
            )
            count = result.scalar() or 0
            funnel_data[stage] = count

        # Calculate conversion rates
        stages_with_rates = []
        previous_count = None
        for stage in self.FUNNEL_STAGES:
            count = funnel_data[stage]
            rate = None
            if previous_count is not None and previous_count > 0:
                rate = round((count / previous_count) * 100, 2)
            stages_with_rates.append({
                "stage": stage,
                "count": count,
                "conversion_rate": rate,
            })
            previous_count = count

        return {
            "stages": stages_with_rates,
            "period_days": days,
        }

    async def get_social_funnel(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Social funnel per spec §3.

        Comment/DM -> Reply -> Product viewed -> Checkout created ->
        Payment started -> Paid. Counts derive from events, messages,
        checkouts and payments — never manual entry.
        """
        from datetime import datetime, timedelta

        from infalette_database.models.message import Message
        from infalette_database.models.payment import Payment
        from infalette_database.models.conversation import Conversation

        start_date = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(func.count()).where(
                Event.tenant_id == tenant_id,
                Event.event_type == "conversation.message_received",
                Event.created_at >= start_date,
            )
        )
        received = result.scalar() or 0

        # Outbound replies recorded as messages (automation or agent)
        result = await session.execute(
            select(func.count(Message.id))
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == tenant_id,
                Message.created_at >= start_date,
                Message.direction == "outbound",
            )
        )
        reply_sent = result.scalar() or 0
        product_viewed = await self._stage_event_count(
            tenant_id, ["product.viewed"], start_date, session
        )
        checkout_created = await self._stage_event_count(
            tenant_id, ["checkout.created"], start_date, session
        )

        result = await session.execute(
            select(func.count()).where(
                Payment.tenant_id == tenant_id,
                Payment.provider != "cod",
                Payment.created_at >= start_date,
            )
        )
        payment_started = result.scalar() or 0

        paid = await self._stage_event_count(
            tenant_id, ["payment.succeeded", "order.cod_created"], start_date, session
        )

        stages = [
            ("comment_or_dm_received", received),
            ("reply_sent", reply_sent),
            ("product_viewed", product_viewed),
            ("checkout_created", checkout_created),
            ("payment_started", payment_started),
            ("paid", paid),
        ]
        stages_with_rates = []
        previous = None
        for name, count in stages:
            rate = (
                round((count / previous) * 100, 2)
                if previous not in (None, 0)
                else None
            )
            stages_with_rates.append({"stage": name, "count": count, "conversion_rate": rate})
            previous = count if count else previous

        return {"stages": stages_with_rates, "period_days": days}

    async def _stage_event_count(
        self,
        tenant_id: UUID,
        event_types: list,
        start_date,
        session: AsyncSession,
    ) -> int:
        result = await session.execute(
            select(func.count()).where(
                Event.tenant_id == tenant_id,
                Event.event_type.in_(event_types),
                Event.created_at >= start_date,
            )
        )
        return result.scalar() or 0

    async def get_checkout_funnel(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Get the checkout funnel for a tenant."""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Checkout started
        result = await session.execute(
            select(func.count()).where(
                Checkout.tenant_id == tenant_id,
                Checkout.created_at >= start_date,
            )
        )
        checkout_started = result.scalar() or 0

        # Checkout completed (paid)
        result = await session.execute(
            select(func.count()).where(
                Checkout.tenant_id == tenant_id,
                Checkout.status == "paid",
                Checkout.created_at >= start_date,
            )
        )
        checkout_completed = result.scalar() or 0

        # Orders created
        result = await session.execute(
            select(func.count()).where(
                Order.tenant_id == tenant_id,
                Order.created_at >= start_date,
            )
        )
        orders_created = result.scalar() or 0

        return {
            "checkout_started": checkout_started,
            "checkout_completed": checkout_completed,
            "orders_created": orders_created,
            "checkout_conversion_rate": round(
                (checkout_completed / checkout_started * 100) if checkout_started > 0 else 0, 2
            ),
            "order_conversion_rate": round(
                (orders_created / checkout_completed * 100) if checkout_completed > 0 else 0, 2
            ),
        }

    async def get_lead_funnel(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Get the lead funnel for a tenant."""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(func.count()).where(
                Lead.tenant_id == tenant_id,
                Lead.created_at >= start_date,
            )
        )
        total_leads = result.scalar() or 0

        result = await session.execute(
            select(func.count()).where(
                Lead.tenant_id == tenant_id,
                Lead.status == "converted",
                Lead.created_at >= start_date,
            )
        )
        converted_leads = result.scalar() or 0

        return {
            "total_leads": total_leads,
            "converted_leads": converted_leads,
            "conversion_rate": round(
                (converted_leads / total_leads * 100) if total_leads > 0 else 0, 2
            ),
        }
