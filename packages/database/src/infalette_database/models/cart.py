"""Cart model."""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class Cart(Base, TenantMixin):
    """Cart model.

    Shopping cart for a customer or guest session.
    """

    __tablename__ = "carts"

    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    # Guest carts are keyed by an opaque session key (X-Cart-Session-ID)
    session_key = Column(String(64), nullable=True, index=True)
    total_cents = Column(Integer, default=0, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
