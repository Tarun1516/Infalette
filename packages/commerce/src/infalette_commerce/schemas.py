"""Commerce-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from infalette_validation.schemas import (
    OrderStatus,
    PaymentStatus,
    PaymentProvider,
    CheckoutStatus,
)

# Re-export COD support: ensure PaymentProvider includes COD via validation schema
# (cod provider is defined in infalette_validation.schemas.PaymentProvider)


class CartRead(BaseModel):
    """Schema for reading a cart."""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    customer_id: Optional[UUID]
    total_cents: int
    currency: str
    items: list["CartItemRead"] = Field(default_factory=list)


class CartItemRead(BaseModel):
    """Schema for reading a cart item."""

    model_config = {"from_attributes": True}

    id: UUID
    cart_id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    quantity: int
    price_cents: int


class CheckoutRead(BaseModel):
    """Schema for reading a checkout."""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    customer_id: Optional[UUID]
    cart_id: UUID
    total_cents: int
    currency: str
    status: CheckoutStatus
    attribution: dict
    expires_at: Optional[datetime]


class OrderCreate(BaseModel):
    """Schema for creating an order from a checkout."""

    checkout_id: UUID
    shipping_address: dict
    billing_address: dict


class OrderStatusUpdate(BaseModel):
    """Schema for updating order status."""

    status: OrderStatus
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None


class FulfillmentCreate(BaseModel):
    """Schema for creating a fulfillment."""

    order_id: UUID
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None


class RefundCreate(BaseModel):
    """Schema for creating a refund."""

    payment_id: UUID
    amount_cents: int
    reason: Optional[str] = None


class DiscountCodeValidate(BaseModel):
    """Schema for validating a discount code."""

    code: str
    order_total_cents: int


class ShippingOptionRead(BaseModel):
    """Schema for reading a shipping option."""

    id: str
    name: str
    price_cents: int
    estimated_days: Optional[int] = None
    carrier: Optional[str] = None


class PaymentInitiationResponse(BaseModel):
    """Schema for payment initiation response."""

    checkout_id: UUID
    payment_url: Optional[str] = None
    payment_id: Optional[str] = None
    provider: PaymentProvider
    amount_cents: int
    currency: str
