"""Infalette analytics package."""

from infalette_analytics.event_bus import record_event
try:  # optional publish helper
    from infalette_analytics.event_bus import publish_event  # type: ignore
except ImportError:
    publish_event = record_event  # fallback

from infalette_analytics.aggregator import aggregate_daily_metrics, AnalyticsAggregator
try:
    from infalette_analytics.dashboard import get_sales_dashboard_data  # type: ignore
except ImportError:
    from infalette_analytics.dashboard import DashboardService as get_sales_dashboard_data  # type: ignore

__all__ = [
    "record_event",
    "publish_event",
    "aggregate_daily_metrics",
    "AnalyticsAggregator",
    "get_sales_dashboard_data",
]
