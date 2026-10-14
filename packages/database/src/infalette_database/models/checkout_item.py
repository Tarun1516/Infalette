"""CheckoutItem model."""

from __future__ import annotations

from sqlalchemy import Column, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class CheckoutItem(Base):
    """Checkout item model.

    Immutable snapshot of product name, tax and price inside checkout items.
    """

    __tablename__ = "checkout_items"

    checkout_id = Column(
        UUID(as_uuid=True), ForeignKey("checkouts.id"), nullable=False, index=True
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
