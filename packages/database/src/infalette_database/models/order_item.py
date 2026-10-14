"""OrderItem model."""

from __future__ import annotations

from sqlalchemy import Column, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class OrderItem(Base):
    """Order item model.

    Immutable snapshot of product name, tax and price inside order items.
    """

    __tablename__ = "order_items"

    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id = Column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    variant_id = Column(
        UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True
    )
    quantity = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    product_snapshot_json = Column(JSON, nullable=False)
    # Immutable tax snapshot (spec §7): captured at checkout time so
    # invoices never recompute tax from rates that changed later.
    tax_cents = Column(Integer, nullable=True)
    tax_rate_bps = Column(Integer, nullable=True)
