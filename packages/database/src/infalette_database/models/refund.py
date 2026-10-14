"""Refund model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class RefundStatus(str, enum.Enum):
    """Refund status enum."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Refund(Base):
    """Refund model.

    Refunds for payments.
    """

    __tablename__ = "refunds"

    payment_id = Column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True
    )
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(
        SAEnum(RefundStatus, native_enum=False, length=50), default=RefundStatus.PENDING, nullable=False
    )
