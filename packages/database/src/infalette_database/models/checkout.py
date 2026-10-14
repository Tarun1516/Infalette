"""Checkout model."""

from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    ForeignKey,
    DateTime,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class CheckoutStatus(str, enum.Enum):
    """Checkout status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Checkout(Base, TenantMixin):
    """Checkout model.

    Checkout with customer, items, discounts, and attribution.
    Inventory is reserved when checkout begins and confirmed after payment.
    """

    __tablename__ = "checkouts"

    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    cart_id = Column(
        UUID(as_uuid=True), ForeignKey("carts.id"), nullable=False, index=True
    )
    items_json = Column(JSON, nullable=False, default=list)
    discounts_json = Column(JSON, nullable=False, default=list)
    total_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(
        SAEnum(CheckoutStatus, native_enum=False, length=50), default=CheckoutStatus.PENDING, nullable=False
    )
    attribution_json = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime(timezone=True), nullable=True)
