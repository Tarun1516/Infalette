"""DiscountCode model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint

from infalette_database.base import Base, TenantMixin


class DiscountCode(Base, TenantMixin):
    """Discount / coupon code.

    Tenant-scoped coupon codes supporting percentage, fixed amount,
    and free-shipping discounts with usage limits and expiry.
    """

    __tablename__ = "discount_codes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_discount_codes_tenant_code"),
    )

    code = Column(String(50), nullable=False, index=True)
    discount_type = Column(String(20), nullable=False)  # percentage / fixed / free_shipping
    value = Column(Integer, nullable=False)
    minimum_order_cents = Column(Integer, nullable=False, default=0)
    usage_limit = Column(Integer, nullable=True)
    used_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
