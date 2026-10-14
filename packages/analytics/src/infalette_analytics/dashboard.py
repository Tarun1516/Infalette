"""Analytics dashboard service."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.event import Event
from infalette_database.models.order import Order, OrderStatus
from infalette_database.models.order_item import OrderItem
from infalette_database.models.payment import Payment
from infalette_database.models.refund import Refund
from infalette_database.models.customer import Customer
from infalette_database.models.lead import Lead
from infalette_database.models.product import Product
from infalette_database.models.checkout import Checkout
from infalette_analytics.funnel import FunnelAnalyzer


class DashboardService:
    """Analytics dashboard service for generating metrics and reports."""

    def __init__(self) -> None:
        self._funnel = FunnelAnalyzer()

    async def get_dashboard_data(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Get comprehensive dashboard data for a tenant."""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Sales metrics
        result = await session.execute(
            select(
                func.count().label("total_orders"),
                func.sum(Order.total_cents).label("gross_sales"),
                func.avg(Order.total_cents).label("aov"),
            ).where(
                Order.tenant_id == tenant_id,
                Order.created_at >= start_date,
            )
        )
        sales_row = result.fetchone()

        # Refunds for net sales (real value, not an approximation)
        result = await session.execute(
            select(func.coalesce(func.sum(Refund.amount_cents), 0)).join(
                Payment, Refund.payment_id == Payment.id
            ).where(
                Payment.tenant_id == tenant_id,
                Refund.created_at >= start_date,
            )
        )
        refunded_cents = int(result.scalar() or 0)

        # Customer metrics
        result = await session.execute(
            select(func.count()).where(
                Customer.tenant_id == tenant_id,
                Customer.created_at >= start_date,
            )
        )
        total_customers = result.scalar() or 0

        # Lead metrics
        result = await session.execute(
            select(
                func.count(Lead.id).label("total_leads"),
                func.count(Lead.id).filter(Lead.status == "converted").label("converted_leads"),
            ).where(
                Lead.tenant_id == tenant_id,
                Lead.created_at >= start_date,
            )
        )
        lead_row = result.fetchone()

        # Checkout funnel
        funnel = await self._funnel.get_checkout_funnel(tenant_id, session, days)

        # Sales over time
        sales_over_time = await self._get_sales_over_time(tenant_id, session, start_date)

        # Top products
        top_products = await self._get_top_products(tenant_id, session, limit=5)

        # Campaign performance (spec §3: campaign performance on the dashboard)
        campaigns_perf = await self._get_campaign_performance(
            tenant_id, session, start_date
        )

        return {
            "sales": {
                "total_orders": sales_row.total_orders or 0,
                "gross_sales_cents": sales_row.gross_sales or 0,
                "aov_cents": sales_row.aov or 0,
                "net_sales_cents": max((sales_row.gross_sales or 0) - refunded_cents, 0),
            },
            "customers": {
                "total_customers": total_customers,
                "new_customers": total_customers,
            },
            "leads": {
                "total_leads": lead_row.total_leads or 0,
                "converted_leads": lead_row.converted_leads or 0,
                "conversion_rate": round(
                    ((lead_row.converted_leads or 0) / max(lead_row.total_leads or 1, 1)) * 100, 2
                ),
            },
            "funnel": funnel,
            "sales_over_time": sales_over_time,
            "top_products": top_products,
            "campaign_performance": campaigns_perf,
            "period_days": days,
        }

    async def _get_campaign_performance(
        self,
        tenant_id: UUID,
        session,
        start_date,
    ) -> list[dict]:
        """Per-campaign attributed leads/orders/revenue for the window.

        Attribution joins checkout.created events whose ``utm_campaign``
        matches the campaign slug/utm fields.
        """
        from infalette_database.models.campaign import Campaign

        try:
            rows = await session.execute(
                select(Campaign).where(Campaign.tenant_id == tenant_id)
            )
            campaigns = list(rows.scalars().all())
        except Exception:
            return []

        if not campaigns:
            return []

        event_rows = await session.execute(
            select(Event).where(
                Event.tenant_id == tenant_id,
                Event.event_type == "checkout.created",
                Event.created_at >= start_date,
            )
        )
        events = [
            (r[0] or {})
            for r in event_rows.fetchall()
        ]

        performance = []
        for c in campaigns:
            utm_names = {
                str(c.utm_campaign or "").lower(),
                str(c.slug or "").lower(),
            } - {""}
            attributed = [
                e for e in events
                if str(e.get("utm_campaign") or e.get("source") or "").lower() in utm_names
            ]
            revenue = sum(int(e.get("total_cents") or 0) for e in attributed)
            performance.append({
                "campaign_id": str(c.id),
                "name": c.name,
                "status": str(getattr(c.status, "value", c.status) or ""),
                "attributed_checkouts": len(attributed),
                "attributed_revenue_cents": revenue,
            })
        return performance

    async def get_funnel_data(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Get funnel data from events."""
        return await self._funnel.get_funnel(tenant_id, session, days)

    async def get_channel_attribution(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Get channel attribution data from events.

        Uses raw SQL so the JSONB extraction works portably across
        SQLAlchemy versions — the ORM column is declared as plain JSON
        (cross-dialect friendly) but the underlying column is JSONB.
        """
        from sqlalchemy import text as sql_text

        start_date = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            sql_text(
                """
                SELECT COALESCE(payload_json->>'source', 'unknown') AS channel,
                       COUNT(*) AS count
                FROM events
                WHERE tenant_id = :tenant_id
                  AND event_type = 'checkout.created'
                  AND created_at >= :start_date
                GROUP BY COALESCE(payload_json->>'source', 'unknown')
                """
            ),
            {"tenant_id": str(tenant_id), "start_date": start_date},
        )
        return {
            "channels": [
                {"channel": row.channel or "unknown", "count": int(row.count or 0)}
                for row in result.fetchall()
            ]
        }

    async def get_product_performance(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        limit: int = 10,
    ) -> list[dict]:
        """Get product performance metrics."""
        result = await session.execute(
            select(
                Product.name,
                func.count().label("orders"),
                func.sum(Product.price_cents).label("revenue"),
            )
            .join(Order, Product.id == Order.id)  # Simplified
            .where(Product.tenant_id == tenant_id)
            .group_by(Product.id, Product.name)
            .order_by(func.count().desc())
            .limit(limit)
        )

        return [
            {"name": row.name, "orders": row.orders, "revenue_cents": row.revenue or 0}
            for row in result.fetchall()
        ]

    async def get_low_inventory_alerts(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        threshold: int = 10,
    ) -> list[dict]:
        """Get products with low inventory."""
        result = await session.execute(
            select(Product)
            .where(
                Product.tenant_id == tenant_id,
                Product.inventory_track == True,
                Product.inventory_quantity <= threshold,
            )
            .order_by(Product.inventory_quantity.asc())
        )

        return [
            {"name": p.name, "sku": p.sku, "inventory": p.inventory_quantity}
            for p in result.scalars().all()
        ]

    async def get_repeat_customers(
        self,
        tenant_id: UUID,
        session: AsyncSession,
    ) -> dict:
        """Get repeat customer metrics."""
        result = await session.execute(
            select(
                Customer.id,
                func.count(Order.id).label("order_count"),
            )
            .outerjoin(Order, Customer.id == Order.customer_id)
            .where(Customer.tenant_id == tenant_id)
            .group_by(Customer.id)
            .having(func.count(Order.id) > 1)
        )

        repeat_customers = list(result.fetchall())
        total_customers = await session.execute(
            select(func.count()).where(Customer.tenant_id == tenant_id)
        )
        total = total_customers.scalar() or 0

        return {
            "repeat_customers": len(repeat_customers),
            "total_customers": total,
            "repeat_rate": round(len(repeat_customers) / max(total, 1) * 100, 2),
        }

    async def _get_sales_over_time(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        start_date: datetime,
    ) -> list[dict]:
        """Get sales data over time."""
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

    async def _get_top_products(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        limit: int = 5,
    ) -> list[dict]:
        """Top products by units sold, from order line items."""
        # product_snapshot_json is JSONB. Use the jsonb extraction operator
        # with a CAST to text for the name; some SQLAlchemy versions don't
        # allow `.astext` on the bracket expression depending on the
        # driver, so the raw text() operator is the safe path.
        from sqlalchemy import text as sql_text

        result = await session.execute(
            select(
                OrderItem.product_id.label("product_id"),
                func.sum(OrderItem.quantity).label("units"),
                func.sum(OrderItem.price_cents * OrderItem.quantity).label("revenue"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.tenant_id == tenant_id,
                Order.status != OrderStatus.CANCELLED,
            )
            .group_by(OrderItem.product_id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )
        rows = list(result.fetchall())
        # Resolve product names with a single follow-up query to avoid
        # the JSON bracket-access portability issue entirely.
        product_ids = [r.product_id for r in rows if r.product_id]
        name_map: dict = {}
        if product_ids:
            from infalette_database.models.product import Product as _P

            name_result = await session.execute(
                select(_P.id, _P.name).where(_P.id.in_(product_ids))
            )
            name_map = {pid: nm for pid, nm in name_result.fetchall()}

        return [
            {
                "name": name_map.get(r.product_id) or "Unknown",
                "orders": int(r.units or 0),
                "revenue_cents": int(r.revenue or 0),
            }
            for r in rows
        ]
