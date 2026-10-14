"""Daily metric aggregation from raw events."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.event import Event
from infalette_database.models.metric_daily import MetricDaily
from infalette_database.models.order import Order


async def aggregate_daily_metrics(tenant_id: UUID, target_date: date, session: AsyncSession) -> dict:
    """Aggregate daily metrics from raw events and orders for a single tenant/day.

    Correctly writes to MetricDaily fields: tenant_id, date, metric_name, value, metadata_json
    instead of the legacy metrics_json blob.

    Metrics aggregated per day:
      - total_events
      - orders (event count)
      - payments_succeeded
      - orders_count (DB)
      - gross_sales_cents
      - avg_order_value_cents
    """
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # --- Events ---
    result = await session.execute(
        select(func.count()).where(
            Event.tenant_id == tenant_id,
            Event.created_at >= start,
            Event.created_at < end,
        )
    )
    total_events = result.scalar() or 0

    result = await session.execute(
        select(func.count()).where(
            Event.tenant_id == tenant_id,
            Event.event_type == "order.created",
            Event.created_at >= start,
            Event.created_at < end,
        )
    )
    order_events = result.scalar() or 0

    result = await session.execute(
        select(func.count()).where(
            Event.tenant_id == tenant_id,
            Event.event_type == "payment.succeeded",
            Event.created_at >= start,
            Event.created_at < end,
        )
    )
    payment_events = result.scalar() or 0

    # --- Orders ---
    result = await session.execute(
        select(func.count(), func.coalesce(func.sum(Order.total_cents), 0)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at < end,
        )
    )
    row = result.fetchone()
    orders_count = row[0] if row else 0
    gross_sales = row[1] if row and row[1] is not None else 0
    aov = (gross_sales // orders_count) if orders_count else 0

    metrics: dict[str, tuple[Decimal | int, dict]] = {
        "total_events": (total_events, {"source": "events"}),
        "order_events": (order_events, {"source": "events"}),
        "payments_succeeded": (payment_events, {"source": "events"}),
        "orders_count": (orders_count, {"source": "orders"}),
        "gross_sales_cents": (gross_sales, {"source": "orders"}),
        "avg_order_value_cents": (aov, {"source": "orders"}),
    }

    # Upsert each metric_name as separate row
    for metric_name, (value, meta) in metrics.items():
        # Check existing
        result = await session.execute(
            select(MetricDaily).where(
                MetricDaily.tenant_id == tenant_id,
                MetricDaily.date == target_date,
                MetricDaily.metric_name == metric_name,
            )
        )
        existing = result.scalar_one_or_none()
        # Normalize Decimal for Numeric column
        dec_value = Decimal(str(value)) if not isinstance(value, Decimal) else value
        if existing:
            existing.value = dec_value
            existing.metadata_json = meta
        else:
            metric = MetricDaily(
                tenant_id=tenant_id,
                date=target_date,
                metric_name=metric_name,
                value=dec_value,
                metadata_json=meta,
            )
            session.add(metric)

    await session.commit()
    # Return simple dict for callers
    return {k: v[0] for k, v in metrics.items()}


class AnalyticsAggregator:
    """Aggregator expected by workers and API services.

    Provides aggregate_tenant_metrics (per-tenant over N days) and
    funnel delegation for backwards compatibility with apps.api.modules.analytics.services
    which does `AnalyticsAggregator().get_funnel(...)`.
    """

    async def aggregate_tenant_metrics(
        self, tenant_id: UUID, session: AsyncSession, days: int = 1
    ) -> dict:
        """Aggregate metrics for a tenant over the last `days` days.

        Returns dict mapping date string -> metrics dict.
        """
        results: dict[str, dict] = {}
        today = datetime.now(timezone.utc).date()
        for offset in range(days):
            target = today - timedelta(days=offset)
            metrics = await aggregate_daily_metrics(tenant_id, target, session)
            results[str(target)] = metrics
        return results

    async def get_funnel(
        self, tenant_id: UUID, session: AsyncSession, days: int = 30
    ) -> dict:
        """Delegate to FunnelAnalyzer for funnel data."""
        from infalette_analytics.funnel import FunnelAnalyzer

        analyzer = FunnelAnalyzer()
        return await analyzer.get_funnel(tenant_id, session, days)

    # Compatibility alias – some code may call .aggregate_daily_metrics as method
    async def aggregate_daily_metrics(
        self, tenant_id: UUID, target_date: date, session: AsyncSession
    ) -> dict:
        return await aggregate_daily_metrics(tenant_id, target_date, session)
