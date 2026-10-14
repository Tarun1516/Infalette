"""Payment model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class PaymentStatus(str, enum.Enum):
    """Payment status enum."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentProvider(str, enum.Enum):
    """Payment provider enum."""

    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    COD = "cod"


class Payment(Base, TenantMixin):
    """Payment model.

    Payments through Razorpay or Stripe Connect.
    The signed payment webhook is authoritative for payment confirmation.
    """

    __tablename__ = "payments"

    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, index=True
    )
    provider = Column(
        SAEnum(PaymentProvider, native_enum=False, length=50), nullable=False, index=True
    )
    provider_payment_id = Column(String(255), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(
        SAEnum(PaymentStatus, native_enum=False, length=50), default=PaymentStatus.PENDING, nullable=False
    )
