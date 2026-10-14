"""Cart management services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.cart import Cart
from infalette_database.models.cart_item import CartItem
from infalette_database.models.product import Product
from infalette_validation.schemas import CartItemCreate


async def _recalculate_total(tenant_id: UUID, session: AsyncSession) -> int | None:
    """Recompute and persist the tenant's cart total (sum of item lines)."""
    from sqlalchemy import func

    result = await session.execute(
        select(Cart).where(Cart.tenant_id == tenant_id).order_by(Cart.created_at.desc())
    )
    carts = list(result.scalars().all())
    if not carts:
        return None
    updated = 0
    for cart in carts:
        res = await session.execute(
            select(func.coalesce(func.sum(CartItem.price_cents * CartItem.quantity), 0)).where(
                CartItem.cart_id == cart.id
            )
        )
        total = int(res.scalar() or 0)
        if cart.total_cents != total:
            cart.total_cents = total
            updated += 1
    if updated:
        await session.commit()
    return carts[0].total_cents


async def get_or_create_cart(
    tenant_id: UUID,
    customer_id: UUID | None,
    session: AsyncSession,
    session_key: str | None = None,
) -> Cart:
    """Get or create a cart for a customer or a guest session.

    Authenticated users are keyed by customer_id. Guests (storefront
    without login) are keyed by the opaque ``session_key`` sent via
    ``X-Cart-Session-ID``.
    """
    if customer_id is not None:
        result = await session.execute(
            select(Cart).where(Cart.tenant_id == tenant_id, Cart.customer_id == customer_id)
        )
    elif session_key:
        result = await session.execute(
            select(Cart).where(Cart.tenant_id == tenant_id, Cart.session_key == session_key)
        )
    else:
        raise ValueError("Either customer_id or session_key is required")

    cart = result.scalar_one_or_none()
    if not cart:
        cart = Cart(
            tenant_id=tenant_id,
            customer_id=customer_id,
            session_key=session_key,
            total_cents=0,
        )
        session.add(cart)
        await session.commit()
        await session.refresh(cart)
    return cart


async def add_to_cart(
    tenant_id: UUID,
    customer_id: UUID | None,
    data: CartItemCreate,
    session: AsyncSession,
    session_key: str | None = None,
) -> CartItem:
    """Add an item to the cart."""
    cart = await get_or_create_cart(tenant_id, customer_id, session, session_key=session_key)

    # Check if item already exists in cart
    result = await session.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == data.product_id,
        )
    )
    existing_item = result.scalar_one_or_none()

    if existing_item:
        existing_item.quantity += data.quantity
        await session.commit()
        await session.refresh(existing_item)
        return existing_item

    # Get product price
    result = await session.execute(
        select(Product).where(Product.id == data.product_id, Product.tenant_id == tenant_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise ValueError("Product not found")

    cart_item = CartItem(
        tenant_id=tenant_id,
        cart_id=cart.id,
        product_id=data.product_id,
        variant_id=data.variant_id,
        quantity=data.quantity,
        price_cents=product.price_cents,
    )
    session.add(cart_item)
    await session.commit()
    await session.refresh(cart_item)

    # Funnel instrumentation (spec §3 analytics): add_to_cart stage
    try:
        from infalette_analytics.event_bus import record_event

        await record_event(
            tenant_id=tenant_id,
            actor_id=customer_id,
            event_type="cart.item_added",
            payload={
                "cart_id": str(cart.id),
                "product_id": str(data.product_id),
                "variant_id": str(data.variant_id) if data.variant_id else None,
                "quantity": data.quantity,
                "session_key": session_key,
            },
            session=session,
        )
    except Exception:
        pass

    await _recalculate_total(tenant_id, session)
    return cart_item


async def get_cart_with_items(cart_id: UUID, session: AsyncSession) -> dict:
    """Return cart + items with product names for the storefront."""
    result = await session.execute(select(Cart).where(Cart.id == cart_id))
    cart = result.scalar_one_or_none()
    if not cart:
        return {}
    items = await get_cart_items(cart.id, session)
    item_dicts = []
    for it in items:
        prod_result = await session.execute(
            select(Product).where(Product.id == it.product_id)
        )
        product = prod_result.scalar_one_or_none()
        item_dicts.append({
            "id": str(it.id),
            "product_id": str(it.product_id),
            "name": product.name if product else None,
            "image_url": (product.image_url if product else None),
            "quantity": it.quantity,
            "price_cents": it.price_cents,
        })
    return {
        "id": str(cart.id),
        "total_cents": cart.total_cents,
        "currency": cart.currency,
        "items": item_dicts,
    }


async def get_cart_items(cart_id: UUID, session: AsyncSession) -> list[CartItem]:
    result = await session.execute(select(CartItem).where(CartItem.cart_id == cart_id))
    return list(result.scalars().all())


async def update_cart_item(item_id: UUID, quantity: int, session: AsyncSession, tenant_id: UUID | None = None) -> CartItem | None:
    """Update a cart item quantity with tenant isolation."""
    from sqlalchemy import update
    from fastapi import HTTPException

    # Tenant isolation: ensure cart belongs to tenant
    if tenant_id is not None:
        result = await session.execute(
            select(CartItem).join(Cart, CartItem.cart_id == Cart.id).where(
                CartItem.id == item_id,
                Cart.tenant_id == tenant_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found or access denied")
    await session.execute(
        update(CartItem)
        .where(CartItem.id == item_id)
        .values(quantity=quantity)
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    if tenant_id is not None:
        await _recalculate_total(tenant_id, session)
    # Return with tenant check again
    if tenant_id is not None:
        result = await session.execute(
            select(CartItem).join(Cart, CartItem.cart_id == Cart.id).where(
                CartItem.id == item_id,
                Cart.tenant_id == tenant_id,
            )
        )
    else:
        result = await session.execute(select(CartItem).where(CartItem.id == item_id))
    return result.scalar_one_or_none()


async def remove_from_cart(item_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> None:
    """Remove an item from the cart with tenant isolation."""
    from fastapi import HTTPException

    if tenant_id is not None:
        result = await session.execute(
            select(CartItem).join(Cart, CartItem.cart_id == Cart.id).where(
                CartItem.id == item_id,
                Cart.tenant_id == tenant_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found or access denied")
        await session.execute(delete(CartItem).where(CartItem.id == item_id))
    else:
        await session.execute(delete(CartItem).where(CartItem.id == item_id))
    await session.commit()


async def clear_cart(cart_id: UUID, session: AsyncSession) -> None:
    """Clear all items from the cart."""
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart_id))
    await session.commit()
