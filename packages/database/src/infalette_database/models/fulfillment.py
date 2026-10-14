"""Fulfillment model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class FulfillmentStatus(str, enum.Enum):
    """Fulfillment status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURNED = "returned"


class Fulfillment(Base):
    """Fulfillment model.

    Order fulfillment with tracking information.
    """

    __tablename__ = "fulfillments"

    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    tracking_number = Column(String(255), nullable=True)
    carrier = Column(String(100), nullable=True)
    status = Column(
        SAEnum(FulfillmentStatus, native_enum=False, length=50),
        default=FulfillmentStatus.PENDING,
        nullable=False,
    )
