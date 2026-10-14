"""Analytics aggregation task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.event import Event
from infalette_database.models.order import Order
from infalette_database.models.customer import Customer
from infalette_database.models.lead import Lead

try:
    from infalette_analytics.aggregator import AnalyticsAggregator, aggregate_daily_metrics
except ImportError:  # fallback if package not installed
    AnalyticsAggregator = None  # type: ignore
    aggregate_daily_metrics = None  # type: ignore

logger = logging.getLogger(__name__)


async def aggregate_analytics(
    session: AsyncSession,
    tenant_id: UUID = None,
    days: int = 1,
) -> dict:
    """Aggregate analytics for a tenant.

    Uses AnalyticsAggregator if available, otherwise falls back to
    aggregate_daily_metrics directly. Never crashes on missing tenants.
    """
    results: dict[str, dict] = {}

    # Prefer class-based aggregator
    if AnalyticsAggregator is not None:
        try:
            aggregator = AnalyticsAggregator()
        except Exception as e:
            logger.error("Failed to init AnalyticsAggregator: %s", e)
            aggregator = None
        if aggregator is not None:
            if tenant_id:
                try:
                    results[str(tenant_id)] = await aggregator.aggregate_tenant_metrics(
                        tenant_id, session, days
                    )
                except Exception as e:
                    logger.error("aggregate_tenant_metrics failed for %s: %s", tenant_id, e, exc_info=True)
                    results[str(tenant_id)] = {"error": str(e)}
            else:
                try:
                    result = await session.execute(select(func.distinct(Event.tenant_id)))
                    tenant_ids = [r for r in result.scalars().all() if r]
                except Exception as e:
                    logger.error("Failed to list tenant_ids: %s", e)
                    tenant_ids = []
                # If no events, also try orders
                if not tenant_ids:
                    try:
                        result = await session.execute(select(func.distinct(Order.tenant_id)))
                        tenant_ids = [r for r in result.scalars().all() if r]
                    except Exception:
                        pass
                for tid in tenant_ids:
                    try:
                        results[str(tid)] = await aggregator.aggregate_tenant_metrics(tid, session, days)
                    except Exception as e:
                        logger.error("aggregate for %s failed: %s", tid, e, exc_info=True)
                        results[str(tid)] = {"error": str(e)}
            return {
                "tenants_processed": len(results),
                "results": results,
            }

    # Fallback – direct function
    if aggregate_daily_metrics is not None and tenant_id is not None:
        from datetime import date, timedelta as td

        today = datetime.utcnow().date()
        for offset in range(days):
            target = today - td(days=offset)
            try:
                await aggregate_daily_metrics(tenant_id, target, session)
                results[str(target)] = {"status": "ok"}
            except Exception as e:
                logger.error("direct aggregate_daily_metrics failed: %s", e)
                results[str(target)] = {"error": str(e)}
        return {"tenants_processed": 1 if tenant_id else 0, "results": results}

    return {
        "tenants_processed": len(results),
        "results": results,
    }


@shared_task(name="apps.workers.tasks.analytics.aggregate_analytics")
def aggregate_analytics_task(tenant_id: str = None, days: int = 1) -> dict:
    """Celery entry point: roll up daily metrics for all tenants."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            tid = UUID(tenant_id) if tenant_id else None
            return await aggregate_analytics(session, tenant_id=tid, days=days)

    return asyncio.run(_run())
