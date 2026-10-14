"""Order model."""

from __future__ import annotations

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class OrderStatus(str, enum.Enum):
    """Order status enum."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    RETURNED = "returned"


class Order(Base, TenantMixin):
    """Order model.

    Orders with payments, fulfillments, refunds and customer.
    """

    __tablename__ = "orders"

    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    checkout_id = Column(
        UUID(as_uuid=True), ForeignKey("checkouts.id"), nullable=True, index=True
    )
    status = Column(
        SAEnum(OrderStatus, native_enum=False, length=50), default=OrderStatus.PENDING, nullable=False
    )
    total_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    shipping_address_json = Column(JSON, nullable=False, default=dict)
    billing_address_json = Column(JSON, nullable=False, default=dict)
