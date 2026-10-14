"""Analytics management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import Feature, require_feature

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_metrics(
    days: int = Query(default=30),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Full dashboard payload (spec §3's 13 metrics).

    Merges the rich ``DashboardService`` (gross/net/AOV/refunds/funnel/
    sales-over-time/top-products) with the flat key contract the admin
    UI expects (total_sales_cents, net_sales_cents, aov_cents,
    conversion_rate, refunds_cents, series...).
    """
    from apps.api.modules.analytics.services import (
        get_dashboard_metrics,
        get_channel_attribution,
    )
    from infalette_analytics.dashboard import DashboardService

    svc = DashboardService()
    base = await get_dashboard_metrics(user.tenant_id, session, days)
    rich = await svc.get_dashboard_data(user.tenant_id, session, days)
    low_stock = await svc.get_low_inventory_alerts(user.tenant_id, session)
    repeat = await svc.get_repeat_customers(user.tenant_id, session)
    channels = await get_channel_attribution(user.tenant_id, session, days)

    sales = rich.get("sales", {})
    leads = rich.get("leads", {})
    gross = int(sales.get("gross_sales_cents") or 0)
    orders = int(sales.get("total_orders") or 0)

    flat = {
        **base,
        # Flat keys the frontend tiles read (analytics/page.tsx)
        "total_orders": orders or base.get("total_orders"),
        "total_sales_cents": gross,
        "gross_sales_cents": gross,
        "net_sales_cents": int(sales.get("net_sales_cents") or 0),
        "refunds": max(gross - int(sales.get("net_sales_cents") or 0), 0) // 100,
        "refunds_cents": max(gross - int(sales.get("net_sales_cents") or 0), 0),
        # UI formats aov/conversion as currency/ratio itself
        "aov": round((int(sales.get("aov_cents") or 0)) / 100, 2),
        "conversion_rate": (leads.get("conversion_rate") or 0) / 100
        if leads.get("conversion_rate", 0) > 1
        else (leads.get("conversion_rate") or 0),
        "repeat_customers": repeat,
        "low_inventory": low_stock,
        # Chart panels: sales_over_time + series alias with the exact
        # field names the bar charts read (date, sales_cents/value).
        "sales_over_time": [
            {
                "date": str(row.get("date")),
                "orders": row.get("orders", 0),
                "revenue_cents": row.get("revenue_cents", 0),
                "sales_cents": row.get("revenue_cents", 0),
                "value": row.get("revenue_cents", 0),
            }
            for row in (rich.get("sales_over_time") or [])
        ],
        "series": [
            {
                "date": str(row.get("date")),
                "orders": row.get("orders", 0),
                "revenue_cents": row.get("revenue_cents", 0),
                "sales_cents": row.get("revenue_cents", 0),
                "value": row.get("revenue_cents", 0),
            }
            for row in (rich.get("sales_over_time") or [])
        ],
        "funnel": rich.get("funnel"),
        "top_products": rich.get("top_products"),
        "channels": channels,
    }
    return flat


@router.get("/low-inventory")
async def get_low_inventory_route(
    threshold: int = Query(default=10),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Products at/below their low-stock threshold."""
    from infalette_analytics.dashboard import DashboardService

    return await DashboardService().get_low_inventory_alerts(
        user.tenant_id, session, threshold
    )


@router.get("/repeat-customers")
async def get_repeat_customers_route(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Customers with more than one order."""
    from infalette_analytics.dashboard import DashboardService

    return await DashboardService().get_repeat_customers(user.tenant_id, session)


@router.get("/sales")
async def get_sales_analytics(
    days: int = Query(default=30),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Sales over time, wrapped as ``{series: [...]}`` for the charts.

    Each point carries both ``revenue_cents`` and the chart consumers'
    aliases (``sales_cents``/``value``).
    """
    from apps.api.modules.analytics.services import get_sales_analytics

    rows = await get_sales_analytics(user.tenant_id, session, days)
    series = [
        {
            "date": str(row.get("date")),
            "orders": row.get("orders", 0),
            "revenue_cents": row.get("revenue_cents", 0),
            "sales_cents": row.get("revenue_cents", 0),
            "value": row.get("revenue_cents", 0),
        }
        for row in rows
    ]
    return {"series": series}


@router.get("/top-products")
async def get_top_products(
    limit: int = Query(default=10),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get top selling products."""
    from apps.api.modules.analytics.services import get_top_products
    return await get_top_products(user.tenant_id, session, limit)


@router.get("/customers")
async def get_customer_analytics(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get customer analytics."""
    from apps.api.modules.analytics.services import get_customer_analytics
    return await get_customer_analytics(user.tenant_id, session)


@router.get("/funnel", dependencies=[Depends(require_feature(Feature.FUNNEL_ANALYTICS))])
async def get_conversion_funnel(
    days: int = Query(default=30),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get website conversion funnel data (plan-gated)."""
    from apps.api.modules.analytics.services import get_conversion_funnel
    return await get_conversion_funnel(user.tenant_id, session, days)


@router.get(
    "/social-funnel",
    dependencies=[Depends(require_feature(Feature.FUNNEL_FULL))],
)
async def get_social_funnel(
    days: int = Query(default=30),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Social funnel: Comment/DM -> Reply -> View -> Checkout -> Paid (plan-gated)."""
    from infalette_analytics.funnel import FunnelAnalyzer

    return await FunnelAnalyzer().get_social_funnel(user.tenant_id, session, days)


@router.get(
    "/abandoned-segments",
    dependencies=[Depends(require_feature(Feature.ABANDONED_SEGMENTS))],
)
async def get_abandoned_segments(
    hours: int = Query(default=24),
    limit: int = Query(default=50),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Abandoned carts + abandoned social checkouts (CRM plan only)."""
    from apps.api.modules.analytics.services import get_abandoned_segments
    return await get_abandoned_segments(user.tenant_id, session, hours, limit)


@router.get(
    "/attribution",
    dependencies=[Depends(require_feature(Feature.ADVANCED_DASHBOARD))],
)
async def get_channel_attribution(
    days: int = Query(default=30),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Channel attribution breakdown for the tenant."""
    from apps.api.modules.analytics.services import get_channel_attribution
    return await get_channel_attribution(user.tenant_id, session, days)


@router.get("/events")
async def get_event_analytics(
    event_type: Optional[str] = Query(default=None),
    days: int = Query(default=30),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get event analytics."""
    from apps.api.modules.analytics.services import get_event_analytics
    return await get_event_analytics(user.tenant_id, session, event_type, days)
