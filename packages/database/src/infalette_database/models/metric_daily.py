"""MetricDaily model."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from sqlalchemy import Column, String, Date, JSON, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class MetricDaily(Base, TenantMixin):
    """Daily metric model.

    Stores daily aggregate metrics to avoid running charts
    directly against orders and message history.

    Metrics include:
    - gross_sales
    - net_sales
    - orders
    - refunds
    - average_order_value
    - conversion_rate
    - repeat_customers
    - top_products
    - low_inventory
    - channel_attribution
    - campaign_performance

    Alembic schema (001_initial_schema) defines:
      tenant_id, date, metric_name, value, metadata_json
    Legacy field metrics_json has been removed in favor of metric_name/value.
    """

    __tablename__ = "metrics_daily"

    date = Column(Date, nullable=False)
    metric_name = Column(String(100), nullable=False, index=True)
    value = Column(Numeric, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index(
            "idx_metrics_daily_tenant_date_metric",
            "tenant_id",
            "date",
            "metric_name",
            unique=True,
        ),
        Index(
            "idx_metrics_daily_tenant_date",
            "tenant_id",
            "date",
        ),
    )

    # ------------------------------------------------------------------
    # Backward-compatibility aliases
    # ------------------------------------------------------------------
    @property
    def metrics_json(self) -> dict:  # pragma: no cover - legacy shim
        """Legacy accessor – returns combined value/metadata."""
        base = {"value": float(self.value) if self.value is not None else 0}
        if isinstance(self.metadata_json, dict):
            base.update(self.metadata_json)
        return base

    @metrics_json.setter
    def metrics_json(self, val: dict) -> None:  # pragma: no cover
        if isinstance(val, dict) and "value" in val:
            self.value = val.pop("value")
            self.metadata_json = val
        else:
            self.metadata_json = val or {}

    # Optional legacy channel/product scoping kept as metadata fallback
    @property
    def channel(self):  # pragma: no cover
        return (self.metadata_json or {}).get("channel")

    @channel.setter
    def channel(self, val):  # pragma: no cover
        if val is not None:
            md = dict(self.metadata_json or {})
            md["channel"] = val
            self.metadata_json = md

    @property
    def product_id(self):  # pragma: no cover
        return (self.metadata_json or {}).get("product_id")

    @product_id.setter
    def product_id(self, val):  # pragma: no cover
        if val is not None:
            md = dict(self.metadata_json or {})
            md["product_id"] = str(val) if val else None
            self.metadata_json = md
