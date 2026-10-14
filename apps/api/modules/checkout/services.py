"""Checkout management services.

Delegates to infalette_commerce.checkout.CheckoutService for full logic
including discount, tax, shipping, inventory reservation, and COD support.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.cart import Cart
from infalette_database.models.cart_item import CartItem
from infalette_database.models.checkout import Checkout, CheckoutStatus
from infalette_database.models.checkout_item import CheckoutItem
from infalette_database.models.product import Product
from infalette_validation.schemas import CheckoutCreate


async def create_checkout(
    tenant_id: UUID,
    customer_id: UUID | None,
    data: CheckoutCreate,
    session: AsyncSession,
    session_key: str | None = None,
) -> Checkout:
    """Create a checkout from the cart (guest or authenticated).

    Delegates to commerce CheckoutService for full tax/discount/shipping handling.
    Falls back to simple logic if commerce service fails (e.g., in unit tests).
    """
    try:
        from infalette_commerce.checkout import CheckoutService
    except ImportError:
        CheckoutService = None  # minimal environments without the commerce package

    if CheckoutService is not None:
        return await CheckoutService().create_checkout(
            tenant_id, customer_id, data, session, session_key=session_key
        )

    # Fallback simple logic for minimal environments only
    from apps.api.modules.cart.services import get_or_create_cart

    cart = await get_or_create_cart(tenant_id, customer_id, session, session_key=session_key)

    # Get cart items
    result = await session.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    cart_items = list(result.scalars().all())
    if not cart_items:
        raise ValueError("Cart is empty")

    # Build checkout items and calculate total
    checkout_items = []
    total_cents = 0
    for item in cart_items:
        result = await session.execute(
            select(Product).where(Product.id == item.product_id, Product.tenant_id == tenant_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            continue

        price = product.sale_price_cents if product.sale_price_cents else product.price_cents
        item_total = price * item.quantity
        total_cents += item_total

        checkout_items.append({
            "product_id": str(item.product_id),
            "variant_id": str(item.variant_id) if item.variant_id else None,
            "quantity": item.quantity,
            "price_cents": price,
            "product_snapshot": {
                "name": product.name,
                "sku": product.sku,
                "price_cents": price,
            },
        })

    # Create checkout
    checkout = Checkout(
        tenant_id=tenant_id,
        customer_id=customer_id,
        cart_id=cart.id,
        items_json=checkout_items,
        discounts_json=data.discount_codes,
        total_cents=total_cents,
        currency="INR",
        status=CheckoutStatus.PENDING,
        attribution_json={"source": "website"},
        expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    session.add(checkout)
    await session.commit()
    await session.refresh(checkout)
    return checkout


async def get_checkout(tenant_id: UUID, checkout_id: UUID, session: AsyncSession) -> Checkout | None:
    """Get a checkout by ID."""
    result = await session.execute(
        select(Checkout).where(Checkout.id == checkout_id, Checkout.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def initiate_payment(tenant_id: UUID, checkout_id: UUID, provider: str, session: AsyncSession) -> dict:
    """Initiate payment for a checkout via commerce CheckoutService.

    Supports razorpay, stripe, and cod. For cod, creates order directly.
    """
    from infalette_commerce.checkout import CheckoutService
    svc = CheckoutService()
    return await svc.initiate_payment(tenant_id, checkout_id, provider, session)


async def confirm_checkout(checkout_id: UUID, session: AsyncSession) -> "Order | None":
    """Confirm checkout and create order."""
    from infalette_database.models.order import Order, OrderStatus
    from infalette_database.models.checkout import CheckoutStatus

    await session.execute(
        __import__("sqlalchemy").update(Checkout)
        .where(Checkout.id == checkout_id)
        .values(status=CheckoutStatus.PAID)
        .execution_options(synchronize_session="fetch")
    )

    result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
    checkout = result.scalar_one_or_none()
    if not checkout:
        return None

    order = Order(
        tenant_id=checkout.tenant_id,
        customer_id=checkout.customer_id,
        checkout_id=checkout.id,
        status=OrderStatus.CONFIRMED,
        total_cents=checkout.total_cents,
        currency=checkout.currency,
        shipping_address_json=checkout.attribution_json,
        billing_address_json=checkout.attribution_json,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order
