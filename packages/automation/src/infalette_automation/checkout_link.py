"""Checkout link generation for automation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_automation.schemas import TriggerEvent


class CheckoutLinkGenerator:
    """Generates checkout links for abandoned cart recovery and other automations."""

    async def create_link(
        self,
        event: TriggerEvent,
        config: dict,
        session: AsyncSession,
    ) -> str:
        """Create a checkout link for an event."""
        from infalette_database.models.cart import Cart, CartItem
        from infalette_database.models.checkout import Checkout, CheckoutStatus
        from infalette_database.models.checkout_item import CheckoutItem
        from infalette_database.models.product import Product

        customer_id = event.payload.get("customer_id")
        cart_id = event.payload.get("cart_id")

        if not customer_id or not cart_id:
            return ""

        # Get cart items
        result = await session.execute(
            select(CartItem).where(CartItem.cart_id == UUID(cart_id))
        )
        cart_items = list(result.scalars().all())

        if not cart_items:
            return ""

        # Calculate total
        total_cents = 0
        checkout_items = []
        for item in cart_items:
            result = await session.execute(
                select(Product).where(Product.id == item.product_id)
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
            tenant_id=event.tenant_id,
            customer_id=UUID(customer_id),
            cart_id=UUID(cart_id),
            items_json=checkout_items,
            discounts_json=[],
            total_cents=total_cents,
            currency="INR",
            status=CheckoutStatus.PENDING,
            attribution_json={
                "source": "automation",
                "automation_rule_id": str(config.get("rule_id", "")),
            },
            expires_at=datetime.utcnow() + timedelta(hours=48),
        )
        session.add(checkout)
        await session.flush()

        # Create checkout items
        for item_data in checkout_items:
            checkout_item = CheckoutItem(
                checkout_id=checkout.id,
                product_id=UUID(item_data["product_id"]),
                variant_id=UUID(item_data["variant_id"]) if item_data["variant_id"] else None,
                quantity=item_data["quantity"],
                price_cents=item_data["price_cents"],
                product_snapshot_json=item_data["product_snapshot"],
            )
            session.add(checkout_item)

        await session.commit()

        # Funnel/attribution: automation-recovered checkouts must appear in
        # the funnel and channel attribution like any other checkout.
        try:
            from infalette_analytics.event_bus import record_event

            await record_event(
                tenant_id=event.tenant_id,
                actor_id=UUID(customer_id),
                event_type="checkout.created",
                payload={
                    "checkout_id": str(checkout.id),
                    "total_cents": total_cents,
                    "customer_id": str(customer_id),
                    "lead_id": event.payload.get("lead_id"),
                    "source": "automation",
                    "automation_rule_id": str(config.get("rule_id", "")),
                },
                session=session,
            )
        except Exception:
            pass

        # Signed tracking token so attribution survives the redirect even
        # if the shopper shares/copies the link.
        import hashlib
        import hmac as _hmac

        from infalette_config import get_settings

        settings = get_settings()
        base_url = config.get("base_url") or str(settings.storefront_url).rstrip("/")
        token_payload = f"{checkout.id}:{event.tenant_id}"
        token_sig = _hmac.new(
            str(settings.auth.secret_key).encode(),
            token_payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        return (
            f"{base_url}/checkout/{checkout.id}"
            f"?utm_source=automation&rule={config.get('rule_id', '')}"
            f"&token={token_sig}"
        )

    async def get_checkout_link(
        self,
        checkout_id: UUID,
        session: AsyncSession,
        tenant_id: Optional[UUID] = None,
    ) -> Optional[str]:
        """Get a checkout link by checkout ID (tenant-scoped when given)."""
        from infalette_database.models.checkout import Checkout

        query = select(Checkout).where(Checkout.id == checkout_id)
        if tenant_id is not None:
            query = query.where(Checkout.tenant_id == tenant_id)
        result = await session.execute(query)
        checkout = result.scalar_one_or_none()
        if not checkout:
            return None

        from infalette_config import get_settings

        base_url = str(get_settings().storefront_url).rstrip("/")
        return f"{base_url}/checkout/{checkout.id}"
