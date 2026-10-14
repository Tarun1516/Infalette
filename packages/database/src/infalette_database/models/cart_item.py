"""CartItem model."""

from __future__ import annotations

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class CartItem(Base):
    """Cart item model.

    Individual items within a cart.
    """

    __tablename__ = "cart_items"

    # tenant_id was added by migration 006 to enable row-level security on
    # child tables. The service populates it from the parent cart so we
    # keep it as a plain FK here rather than re-using the TenantMixin.
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    cart_id = Column(
        UUID(as_uuid=True), ForeignKey("carts.id"), nullable=False, index=True
    )
    product_id = Column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    variant_id = Column(
        UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True
    )
    quantity = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
