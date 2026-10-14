"""Cart management service."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.cart import Cart
from infalette_database.models.cart_item import CartItem
from infalette_database.models.product import Product
from infalette_commerce.pricing import calculate_total
from infalette_commerce.inventory import reserve_inventory, release_inventory


class CartService:
    """Cart management with inventory reservation and pricing."""

    async def get_or_create_cart(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        session: AsyncSession,
    ) -> Cart:
        """Get or create a cart for the customer."""
        result = await session.execute(
            select(Cart).where(
                Cart.tenant_id == tenant_id,
                Cart.customer_id == customer_id,
            )
        )
        cart = result.scalar_one_or_none()
        if not cart:
            cart = Cart(
                tenant_id=tenant_id,
                customer_id=customer_id,
                total_cents=0,
            )
            session.add(cart)
            await session.commit()
            await session.refresh(cart)
        return cart

    async def add_to_cart(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        product_id: UUID,
        quantity: int,
        session: AsyncSession,
        variant_id: Optional[UUID] = None,
    ) -> CartItem:
        """Add an item to the cart with inventory check."""
        cart = await self.get_or_create_cart(tenant_id, customer_id, session)

        # Check if item already exists in cart
        result = await session.execute(
            select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.product_id == product_id,
            )
        )
        existing_item = result.scalar_one_or_none()

        if existing_item:
            existing_item.quantity += quantity
            await session.commit()
            await session.refresh(existing_item)
            return existing_item

        # Get product price and check inventory
        result = await session.execute(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise ValueError("Product not found")

        if product.inventory_track and product.inventory_quantity < quantity:
            raise ValueError("Insufficient inventory")

        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            variant_id=variant_id,
            quantity=quantity,
            # Sale price when active — keeps cart total consistent with
            # the checkout recalculation (which uses sale price).
            price_cents=(
                product.sale_price_cents
                if getattr(product, "sale_price_cents", None)
                else product.price_cents
            ),
        )
        session.add(cart_item)
        await session.commit()
        await session.refresh(cart_item)

        # Update cart total
        await self.calculate_cart_total(cart.id, session)

        return cart_item

    async def update_cart_item(
        self,
        item_id: UUID,
        quantity: int,
        session: AsyncSession,
    ) -> CartItem | None:
        """Update a cart item quantity."""
        from sqlalchemy import update
        await session.execute(
            update(CartItem)
            .where(CartItem.id == item_id)
            .values(quantity=quantity)
            .execution_options(synchronize_session="fetch")
        )
        await session.commit()
        result = await session.execute(select(CartItem).where(CartItem.id == item_id))
        return result.scalar_one_or_none()

    async def remove_from_cart(
        self,
        item_id: UUID,
        session: AsyncSession,
    ) -> None:
        """Remove an item from the cart."""
        await session.execute(delete(CartItem).where(CartItem.id == item_id))
        await session.commit()

    async def clear_cart(
        self,
        cart_id: UUID,
        session: AsyncSession,
    ) -> None:
        """Clear all items from the cart."""
        await session.execute(delete(CartItem).where(CartItem.cart_id == cart_id))
        await session.commit()

    async def calculate_cart_total(
        self,
        cart_id: UUID,
        session: AsyncSession,
    ) -> int:
        """Calculate the total for a cart."""
        result = await session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id)
        )
        items = list(result.scalars().all())

        total = calculate_total(items)

        from sqlalchemy import update
        await session.execute(
            update(Cart)
            .where(Cart.id == cart_id)
            .values(total_cents=total)
            .execution_options(synchronize_session="fetch")
        )
        await session.commit()

        return total

    async def get_cart_items(
        self,
        cart_id: UUID,
        session: AsyncSession,
    ) -> list[CartItem]:
        """Get all items in a cart."""
        result = await session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id)
        )
        return list(result.scalars().all())

    async def apply_discount_code(
        self,
        cart_id: UUID,
        discount_code: str,
        session: AsyncSession,
    ) -> dict:
        """Apply a discount code to the cart."""
        from infalette_commerce.discounts import DiscountService
        discount_service = DiscountService()

        # Get cart total
        result = await session.execute(
            select(Cart).where(Cart.id == cart_id)
        )
        cart = result.scalar_one_or_none()
        if not cart:
            raise ValueError("Cart not found")

        # Validate discount code
        try:
            validation = await discount_service.validate_coupon_code(
                discount_code, cart.tenant_id, cart.total_cents, session
            )
        except ValueError as e:
            return {"valid": False, "error": str(e)}

        # Apply discount
        discounted_total = discount_service.apply_coupon(
            cart.total_cents,
            validation["type"],
            validation["value"],
        )

        from sqlalchemy import update
        await session.execute(
            update(Cart)
            .where(Cart.id == cart_id)
            .values(total_cents=discounted_total)
            .execution_options(synchronize_session="fetch")
        )
        await session.commit()

        return {
            "valid": True,
            "original_total": cart.total_cents,
            "discounted_total": discounted_total,
            "discount_amount": cart.total_cents - discounted_total,
        }
