"""Discount and coupon logic."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.discount_code import DiscountCode


class DiscountService:
    """Coupon and discount logic."""

    async def validate_coupon_code(
        self,
        code: str,
        tenant_id: UUID,
        order_total_cents: int,
        session: AsyncSession,
    ) -> dict:
        """Validate a coupon code against order total."""
        result = await session.execute(
            select(DiscountCode).where(
                DiscountCode.code == code,
                DiscountCode.tenant_id == tenant_id,
            )
        )
        discount = result.scalar_one_or_none()
        if not discount:
            raise ValueError("Invalid coupon code")

        if not discount.is_active:
            raise ValueError("Coupon is not active")

        if discount.expires_at and datetime.utcnow() > discount.expires_at:
            raise ValueError("Coupon has expired")

        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            raise ValueError("Coupon usage limit reached")

        if order_total_cents < discount.minimum_order_cents:
            raise ValueError(
                f"Minimum order amount is {discount.minimum_order_cents} cents"
            )

        return {
            "code": discount.code,
            "type": discount.discount_type,
            "value": discount.value,
            "discount_id": discount.id,
            "discount": discount,
            "valid": True,
        }

    def apply_coupon(
        self,
        price_cents: int,
        discount_type: str,
        value: int,
    ) -> int:
        """Apply a coupon to a price."""
        if discount_type == "percentage":
            return price_cents - (price_cents * value // 100)
        elif discount_type == "fixed":
            return max(price_cents - value, 0)
        elif discount_type == "free_shipping":
            return price_cents  # Shipping discount handled separately
        return price_cents

    def calculate_discount_amount(
        self,
        price_cents: int,
        discount_type: str,
        value: int,
    ) -> int:
        """Calculate the discount amount."""
        if discount_type == "percentage":
            return price_cents * value // 100
        elif discount_type == "fixed":
            return min(value, price_cents)
        return 0

    def check_coupon_validity(
        self,
        discount,
        order_total_cents: int,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Check if a coupon is valid for the given order."""
        if current_time is None:
            current_time = datetime.utcnow()

        if not getattr(discount, "is_active", True):
            return False

        if discount.expires_at and current_time > discount.expires_at:
            return False

        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            return False

        if order_total_cents < discount.minimum_order_cents:
            return False

        return True

    async def increment_usage_count(
        self,
        discount_id: UUID,
        session: AsyncSession,
    ) -> None:
        """Increment the usage count for a discount code."""
        from sqlalchemy import update
        await session.execute(
            update(DiscountCode)
            .where(DiscountCode.id == discount_id)
            .values(used_count=DiscountCode.used_count + 1)
            .execution_options(synchronize_session="fetch")
        )
        await session.commit()
