"""Checkout service with payment integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.cart import Cart
from infalette_database.models.cart_item import CartItem
from infalette_database.models.checkout import Checkout, CheckoutStatus
from infalette_database.models.checkout_item import CheckoutItem
from infalette_database.models.order import Order, OrderStatus
from infalette_database.models.payment import Payment, PaymentStatus, PaymentProvider
from infalette_database.models.product import Product
from infalette_database.models.event import Event
from infalette_database.models.customer import Customer
from infalette_commerce.discounts import DiscountService
from infalette_commerce.inventory import (
    reserve_inventory,
    release_inventory,
    reserve_inventory_atomic,
)
from infalette_commerce.pricing import calculate_total, apply_discount, calculate_tax
from infalette_commerce.shipping import ShippingService
from infalette_commerce.tax import TaxService
from infalette_analytics.event_bus import record_event
from infalette_integrations.razorpay.client import RazorpayClient
from infalette_integrations.stripe.client import StripeClient
from infalette_validation.schemas import CheckoutCreate


def _resolve_lead_hint(session_key: Optional[str]) -> Optional[str]:
    """Best-effort lead linkage from a guest session key.

    Social-generated carts use ``wa-{phone}`` / ``ig-{handle}`` session
    keys; the corresponding lead email convention is
    ``{identifier}@whatsapp.com`` / ``@instagram.com``.
    """
    if not session_key:
        return None
    key = str(session_key)
    for prefix, domain in (("wa-", "whatsapp.com"), ("ig-", "instagram.com")):
        if key.startswith(prefix):
            identifier = key[len(prefix):]
            if identifier:
                return f"lead:{identifier}@{domain}"
    return None


async def _resolve_campaign_id(tenant_id: UUID, slug: str, session: AsyncSession) -> Optional[UUID]:
    """Resolve a ``utm_campaign`` value to the tenant's Campaign id.

    Matches the campaign slug, name, or its configured ``utm_campaign``
    tag so web checkouts attribute to campaigns exactly like the social
    paths do.
    """
    try:
        from infalette_database.models.campaign import Campaign

        value = str(slug).strip()
        result = await session.execute(
            select(Campaign).where(
                Campaign.tenant_id == tenant_id,
                (Campaign.slug == value)
                | (Campaign.name == value)
                | (Campaign.utm_campaign == value),
            ).limit(1)
        )
        campaign = result.scalar_one_or_none()
        return campaign.id if campaign else None
    except Exception:
        return None


class CheckoutService:
    """Checkout creation, payment initiation, and webhook processing."""

    def __init__(self) -> None:
        self._razorpay = RazorpayClient()
        self._stripe = StripeClient()

    async def create_checkout(
        self,
        tenant_id: UUID,
        customer_id: Optional[UUID],
        data: CheckoutCreate,
        session: AsyncSession,
        session_key: Optional[str] = None,
        source: str = "website",
    ) -> Checkout:
        """Create a checkout from the cart with inventory reservation.

        ``customer_id`` may be None for guest checkout; in that case the
        customer is resolved/created from ``data.customer_data`` (email ->
        phone dedup) and the cart is located via ``session_key``.
        """
        # Get or create customer (email -> phone -> create; profile convergence)
        from infalette_commerce.customers import find_or_create_customer

        customer = await find_or_create_customer(
            tenant_id,
            session,
            email=getattr(data.customer_data, "email", None),
            phone=getattr(data.customer_data, "phone", None),
            first_name=getattr(data.customer_data, "first_name", None),
            last_name=getattr(data.customer_data, "last_name", None),
        )

        # Guest: adopt the resolved/created customer identity going forward
        if customer_id is None and customer is not None:
            customer_id = customer.id

        # Get cart — by customer first, then by guest session key
        result = await session.execute(
            select(Cart).where(
                Cart.tenant_id == tenant_id,
                Cart.customer_id == customer_id,
            )
        )
        cart = result.scalar_one_or_none()
        if not cart and session_key:
            result = await session.execute(
                select(Cart).where(
                    Cart.tenant_id == tenant_id,
                    Cart.session_key == session_key,
                )
            )
            cart = result.scalar_one_or_none()
            if cart is not None:
                # Bind guest cart to the customer going forward
                cart.customer_id = customer_id
                await session.flush()
        if not cart:
            raise ValueError("Cart is empty")

        # Get cart items
        result = await session.execute(
            select(CartItem).where(CartItem.cart_id == cart.id)
        )
        cart_items = list(result.scalars().all())
        if not cart_items:
            raise ValueError("Cart is empty")

        # Reserve inventory transaction-safely (spec §3): all items in one
        # shot — variant-aware; any failure releases earlier deductions.
        reservations = [
            (item.product_id, item.quantity, item.variant_id)
            for item in cart_items
        ]
        all_reserved = await reserve_inventory_atomic(reservations, session)
        if not all_reserved:
            await session.rollback()
            raise ValueError("Insufficient inventory for one or more items in cart")

        # Build checkout items and calculate total
        checkout_items = []
        subtotal = 0
        product_tax_map: dict[str, str] = {}
        for item in cart_items:
            result = await session.execute(
                select(Product).where(
                    Product.id == item.product_id,
                    Product.tenant_id == tenant_id,
                )
            )
            product = result.scalar_one_or_none()
            if not product:
                continue

            price = product.sale_price_cents if product.sale_price_cents else product.price_cents
            item_total = price * item.quantity
            subtotal += item_total
            tax_class = getattr(product, "tax_class", "standard") or "standard"

            checkout_items.append({
                "product_id": str(item.product_id),
                "variant_id": str(item.variant_id) if item.variant_id else None,
                "quantity": item.quantity,
                "price_cents": price,
                "tax_class": tax_class,
                "product_snapshot": {
                    "name": product.name,
                    "sku": product.sku,
                    "price_cents": price,
                    "tax_class": tax_class,
                    # Immutable tax + weight snapshots for invoices/shipping
                    "dimensions": getattr(product, "dimensions_json", None) or {},
                    "ingredients": getattr(product, "ingredients", None),
                    "safety_info": getattr(product, "safety_info", None),
                    "age_suitability": (
                        getattr(product.age_suitability, "value", product.age_suitability)
                        if getattr(product, "age_suitability", None) is not None
                        else None
                    ),
                    "pregnancy_stage": (
                        getattr(product.pregnancy_stage, "value", product.pregnancy_stage)
                        if getattr(product, "pregnancy_stage", None) is not None
                        else None
                    ),
                },
            })
            product_tax_map[str(item.product_id)] = tax_class

        # Apply discounts via DiscountService with real validation
        discount_codes = data.discount_codes or []
        total_cents = subtotal
        discount_service = DiscountService()
        has_free_shipping = False
        for code in discount_codes:
            try:
                validation = await discount_service.validate_coupon_code(
                    code=code,
                    tenant_id=tenant_id,
                    order_total_cents=total_cents,
                    session=session,
                )
                discount_type = validation["type"]
                value = validation["value"]
                if discount_type == "free_shipping":
                    has_free_shipping = True
                else:
                    total_cents = discount_service.apply_coupon(total_cents, discount_type, value)
                # Usage counted at payment confirmation (see _confirm_checkout),
                # not at checkout creation — abandoned checkouts must not burn
                # limited-use coupons.
            except ValueError:
                # invalid / expired / inactive coupon: skip
                continue

        # Calculate tax per item based on product tax_class via TaxService.
        # A tenant-level flat override applies when a product has no class.
        tax_service = TaxService()
        shipping_address_dict = {}
        if data.shipping_address:
            try:
                shipping_address_dict = data.shipping_address.model_dump()
            except AttributeError:
                shipping_address_dict = dict(data.shipping_address)

        # Load the tenant's store once (tax override + shipping rules).
        store_row = None
        store_tax_override: Optional[int] = None
        store_rules: dict = {}
        try:
            from infalette_database.models.store import Store as _Store

            _srow = await session.execute(
                select(_Store).where(_Store.tenant_id == tenant_id).limit(1)
            )
            store_row = _srow.scalars().first()
            if store_row is not None:
                if getattr(store_row, "tax_rate", None):
                    store_tax_override = int(store_row.tax_rate)
                if getattr(store_row, "shipping_rules_json", None):
                    store_rules = dict(store_row.shipping_rules_json)
        except Exception:
            store_row = None

        tax_amount = 0
        for item_data in checkout_items:
            item_tax_class = item_data.get("tax_class") or item_data.get("product_snapshot", {}).get("tax_class", "")
            item_total = item_data["price_cents"] * item_data["quantity"]
            # Class-driven slab; tenant flat override when class is empty
            item_tax = tax_service.calculate_tax(
                item_total,
                item_tax_class,
                shipping_address_dict,
                store_override=store_tax_override,
            )
            # Immutable per-item tax snapshot (spec §7): frozen now so
            # invoices never recompute from rates changed later.
            item_rate = tax_service.get_tax_rate(item_tax_class)
            item_data["tax_cents"] = item_tax
            item_data["tax_rate_bps"] = int(round(item_rate * 10000))
            item_data["product_snapshot"]["tax_cents"] = item_tax
            item_data["product_snapshot"]["tax_rate_bps"] = item_data["tax_rate_bps"]
            tax_amount += item_tax
        total_cents += tax_amount

        # Calculate shipping via ShippingService if shipping_address present
        shipping_cost = 0
        if data.shipping_address:
            if not has_free_shipping:
                shipping_service = ShippingService(rules=store_rules)
                zone = shipping_address_dict.get("state", "") or shipping_address_dict.get("country", "") or "default"
                # Real weight from product dimensions_json.weight_kg; 0.5kg per unit fallback
                weight_kg = 0.0
                for item_data in checkout_items:
                    dims = (
                        item_data.get("product_snapshot", {}).get("dimensions")
                        or item_data.get("dimensions_json")
                        or {}
                    )
                    try:
                        item_weight = float((dims or {}).get("weight_kg") or 0.5)
                    except (TypeError, ValueError):
                        item_weight = 0.5
                    weight_kg += item_weight * item_data["quantity"]
                if weight_kg <= 0:
                    weight_kg = 0.5
                # Use current total (after discounts and tax) for free-shipping threshold check inside service
                try:
                    shipping_result = await shipping_service.get_shipping_cost(
                        zone=zone,
                        weight_kg=weight_kg,
                        order_total_cents=total_cents,
                        shipping_type="standard",
                        destination_pincode=shipping_address_dict.get("postal_code"),
                        destination_country=shipping_address_dict.get("country", "India"),
                        declared_value_cents=total_cents,
                        cod=False,
                    )
                    shipping_cost = int(shipping_result.get("price_cents", 0))
                except Exception:
                    shipping_cost = 0
            else:
                shipping_cost = 0
            total_cents += shipping_cost

        # --- Attribution (web UTM / campaign, spec §3 attribution) ---
        attribution_data = getattr(data, "attribution", None)
        attribution_dict: dict = {}
        if attribution_data is not None:
            try:
                attribution_dict = attribution_data.model_dump(exclude_none=True)
            except AttributeError:
                attribution_dict = dict(attribution_data)
        effective_source = (
            attribution_dict.get("source")
            or attribution_dict.get("utm_source")
            or source
        )
        attribution_dict["source"] = effective_source
        campaign_id = attribution_dict.get("campaign_id")
        if campaign_id is None and attribution_dict.get("utm_campaign"):
            campaign_id = await _resolve_campaign_id(
                tenant_id, attribution_dict["utm_campaign"], session
            )
        if campaign_id:
            attribution_dict["campaign_id"] = str(campaign_id)

        # Create checkout
        checkout = Checkout(
            tenant_id=tenant_id,
            customer_id=customer_id,
            cart_id=cart.id,
            items_json=checkout_items,
            discounts_json=discount_codes,
            total_cents=total_cents,
            currency="INR",
            status=CheckoutStatus.PENDING,
            attribution_json={
                **attribution_dict,
                "shipping_address": data.shipping_address.model_dump(),
                "billing_address": data.billing_address.model_dump(),
            },
            expires_at=datetime.utcnow() + timedelta(hours=2),
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

        # Record event — carries source (channel attribution), customer and
        # lead linkage (abandoned-social segment + stage progression join).
        # Real lead ids go in lead_id; social session hints go in lead_hint
        # (a "lead:{email}" string) so consumers never mistake them for UUIDs.
        await record_event(
            tenant_id=tenant_id,
            actor_id=customer_id,
            event_type="checkout.created",
            payload={
                "checkout_id": str(checkout.id),
                "total_cents": total_cents,
                "customer_id": str(customer_id) if customer_id else None,
                "lead_id": getattr(data, "lead_id", None),
                "lead_hint": (
                    _resolve_lead_hint(session_key)
                    if not getattr(data, "lead_id", None)
                    else None
                ),
                "source": effective_source,
                # Campaign attribution join keys (dashboard campaign perf
                # matches checkout.created events on utm_campaign).
                "campaign_id": str(campaign_id) if campaign_id else None,
                "utm_source": attribution_dict.get("utm_source"),
                "utm_medium": attribution_dict.get("utm_medium"),
                "utm_campaign": attribution_dict.get("utm_campaign"),
                "utm_content": attribution_dict.get("utm_content"),
                "utm_term": attribution_dict.get("utm_term"),
            },
            session=session,
        )

        await session.commit()
        await session.refresh(checkout)
        return checkout

    async def initiate_payment(
        self,
        tenant_id: UUID,
        checkout_id: UUID,
        payment_provider: str,
        session: AsyncSession,
    ) -> dict:
        """Initiate payment for a checkout."""
        result = await session.execute(
            select(Checkout).where(
                Checkout.id == checkout_id,
                Checkout.tenant_id == tenant_id,
            )
        )
        checkout = result.scalar_one_or_none()
        if not checkout:
            raise ValueError("Checkout not found")

        if checkout.status != CheckoutStatus.PENDING:
            raise ValueError(f"Checkout is not in pending status (current: {checkout.status})")

        # Normalize provider string
        provider_normalized = payment_provider.lower().strip() if isinstance(payment_provider, str) else str(payment_provider).lower()

        # --- COD flow: create order directly without external payment ---
        if provider_normalized == "cod":
            # Create COD payment record with PENDING (cash to be collected) and immediately confirm order
            payment = Payment(
                tenant_id=tenant_id,
                order_id=None,
                provider=PaymentProvider.COD,
                provider_payment_id=f"cod_{checkout.id.hex}",
                amount_cents=checkout.total_cents,
                currency=checkout.currency,
                status=PaymentStatus.PENDING,
            )
            session.add(payment)
            await session.flush()

            # Update checkout to PROCESSING before confirming
            await session.execute(
                update(Checkout)
                .where(Checkout.id == checkout_id)
                .values(status=CheckoutStatus.PROCESSING)
                .execution_options(synchronize_session="fetch")
            )
            await session.flush()

            # Directly create order (COD orders are CONFIRMED without payment webhook)
            order = await self._confirm_checkout(checkout_id, payment, session)

            # For COD, keep payment as PENDING (or mark as SUCCEEDED if business wants immediate succeeded)
            # We keep PENDING to indicate cash collection pending, but order is CONFIRMED
            await session.commit()
            await session.refresh(payment)
            await session.refresh(order)

            # Record COD event
            await record_event(
                tenant_id=tenant_id,
                actor_id=checkout.customer_id,
                event_type="order.cod_created",
                payload={"order_id": str(order.id), "checkout_id": str(checkout.id), "payment_id": str(payment.id)},
                session=session,
            )
            # record_event may have committed; ensure we still have payment/order refreshed
            return {
                "checkout_id": str(checkout.id),
                "payment_id": str(payment.id),
                "payment_url": None,
                "provider": "cod",
                "amount_cents": checkout.total_cents,
                "currency": checkout.currency,
                "order_id": str(order.id),
                "order_status": order.status.value if hasattr(order.status, "value") else str(order.status),
                "cod": True,
            }

        # Update checkout status for non-COD flows
        await session.execute(
            update(Checkout)
            .where(Checkout.id == checkout_id)
            .values(status=CheckoutStatus.PROCESSING)
            .execution_options(synchronize_session="fetch")
        )

        # Create payment record
        payment = Payment(
            tenant_id=tenant_id,
            order_id=None,  # Will be set after order creation
            provider=PaymentProvider(provider_normalized),
            provider_payment_id="",  # Will be set after payment provider response
            amount_cents=checkout.total_cents,
            currency=checkout.currency,
            status=PaymentStatus.PENDING,
        )
        session.add(payment)
        await session.flush()

        # Resolve tenant's linked merchant account (per-influencer funds routing)
        linked_account_id = await self._resolve_linked_account(tenant_id, provider_normalized, session)

        # Initiate payment with provider
        if provider_normalized == "razorpay":
            payment_data = await self._razorpay.create_payment_link(
                checkout, tenant_id, linked_account_id=linked_account_id
            )
            payment.provider_payment_id = payment_data.get("id", "")
            payment_url = payment_data.get("short_url", "")
        elif provider_normalized == "stripe":
            payment_data = await self._stripe.create_checkout_session(
                checkout, tenant_id, stripe_account_id=linked_account_id
            )
            payment.provider_payment_id = payment_data.get("payment_intent", "")
            payment_url = payment_data.get("url", "")
        elif provider_normalized == "cod":
            # Should have been handled above; fallback
            payment.provider_payment_id = f"cod_{checkout.id.hex}"
            payment_url = ""
        else:
            raise ValueError(f"Unsupported payment provider: {payment_provider}")

        await session.commit()

        return {
            "checkout_id": str(checkout.id),
            "payment_id": str(payment.id),
            "payment_url": payment_url,
            "provider": provider_normalized,
            "amount_cents": checkout.total_cents,
            "currency": checkout.currency,
        }

    async def _resolve_linked_account(
        self,
        tenant_id: UUID,
        provider: str,
        session: AsyncSession,
    ) -> Optional[str]:
        """Resolve the tenant's linked merchant account id, if connected.

        Returns None on any failure so payments still work with platform keys.
        """
        try:
            from infalette_database.models.integration import Integration

            result = await session.execute(
                select(Integration).where(
                    Integration.tenant_id == tenant_id,
                    Integration.provider == provider,
                    Integration.status.in_(("connected", "active")),
                )
            )
            integration = result.scalar_one_or_none()
            if not integration or not integration.credentials_json:
                return None
            creds = dict(integration.credentials_json)
            return (
                creds.get("linked_account_id")
                or creds.get("account_id")
                or creds.get("razorpay_account_id")
                or None
            )
        except Exception:
            return None

    async def process_payment_webhook(
        self,
        provider: str,
        payload: dict,
        signature: str,
        session: AsyncSession,
        raw_body=None,
    ) -> None:
        """Process payment webhook and create order."""
        # Verify webhook signature (providers sign the raw body bytes)
        verification_payload = raw_body if raw_body is not None else payload
        if provider == "razorpay":
            verified = await self._razorpay.verify_webhook_signature(verification_payload, signature)
        elif provider == "stripe":
            verified = await self._stripe.verify_webhook_signature(verification_payload, signature)
        else:
            raise ValueError(f"Unsupported payment provider: {provider}")

        if not verified:
            raise ValueError("Webhook signature verification failed")

        # Extract payment details
        if provider == "razorpay":
            payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id", "")
            checkout_id_str = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {}).get("checkout_id", "")
            status = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("status", "")
        elif provider == "stripe":
            payment_intent = payload.get("data", {}).get("object", {})
            payment_id = payment_intent.get("id", "")
            checkout_id_str = payment_intent.get("metadata", {}).get("checkout_id", "")
            status = payment_intent.get("status", "")

        if not checkout_id_str:
            raise ValueError("Checkout ID not found in webhook payload")

        from uuid import UUID as UUIDType
        checkout_id = UUIDType(checkout_id_str)

        # Find payment
        result = await session.execute(
            select(Payment).where(
                Payment.provider_payment_id == payment_id,
                Payment.provider == PaymentProvider(provider),
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise ValueError("Payment not found")

        # Update payment status
        if status in ("captured", "succeeded", "paid"):
            payment.status = PaymentStatus.SUCCEEDED
        elif status in ("failed", "denied"):
            payment.status = PaymentStatus.FAILED
            # Spec §4 event model: payment.failed
            try:
                await record_event(
                    tenant_id=payment.tenant_id,
                    actor_id=None,
                    event_type="payment.failed",
                    payload={
                        "payment_id": str(payment.id),
                        "provider": provider,
                        "provider_payment_id": payment_id,
                        "checkout_id": str(checkout_id),
                        "amount_cents": payment.amount_cents,
                    },
                    session=session,
                )
            except Exception:
                pass
        else:
            return  # Ignore other statuses

        # If payment succeeded, create order
        if payment.status == PaymentStatus.SUCCEEDED:
            order = await self._confirm_checkout(checkout_id, payment, session)

            # Reload checkout for customer/lead linkage on the event
            checkout_row = (
                await session.execute(
                    select(Checkout).where(Checkout.id == checkout_id)
                )
            ).scalar_one_or_none()

            # Record event — carries lead/customer so the abandoned-social
            # segment and CRM stage progression can join on it.
            def _coalesce(row, attr):
                value = getattr(row, attr, None) if row is not None else None
                return str(value) if value else None

            await record_event(
                tenant_id=payment.tenant_id,
                actor_id=None,
                event_type="payment.succeeded",
                payload={
                    "payment_id": str(payment.id),
                    "order_id": str(order.id),
                    "checkout_id": str(checkout_id),
                    "customer_id": _coalesce(checkout_row, "customer_id"),
                    "lead_id": _coalesce(
                        (getattr(checkout_row, "attribution_json", None) or {}),
                        "lead_id",
                    ),
                },
                session=session,
            )

        await session.commit()

    async def _confirm_checkout(
        self,
        checkout_id: UUID,
        payment: Payment,
        session: AsyncSession,
    ) -> Order:
        """Confirm checkout and create order.

        Idempotent: if this payment already produced an order, or the
        checkout was already paid, the existing order is returned instead
        of creating a duplicate (webhook providers retry deliveries).
        """
        # Guard 1: payment already linked to an order -> replay
        if payment.order_id is not None:
            result = await session.execute(
                select(Order).where(Order.id == payment.order_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        result = await session.execute(
            select(Checkout).where(Checkout.id == checkout_id)
        )
        checkout = result.scalar_one_or_none()
        if not checkout:
            raise ValueError("Checkout not found")

        # Guard 2: an order already exists for this checkout -> replay
        result = await session.execute(
            select(Order).where(Order.checkout_id == checkout_id)
        )
        existing_order = result.scalars().first()
        if existing_order is not None:
            payment.order_id = existing_order.id
            return existing_order

        # Update checkout status
        await session.execute(
            update(Checkout)
            .where(Checkout.id == checkout_id)
            .values(status=CheckoutStatus.PAID)
            .execution_options(synchronize_session="fetch")
        )

        # Coupons are consumed when payment succeeds (not at checkout
        # creation) so abandoned checkouts don't burn limited codes.
        try:
            from infalette_commerce.discounts import DiscountService

            discount_service = DiscountService()
            for code in checkout.discounts_json or []:
                validation = await discount_service.validate_coupon_code(
                    code=code,
                    tenant_id=checkout.tenant_id,
                    order_total_cents=checkout.total_cents,
                    session=session,
                )
                if validation and validation.get("discount_id"):
                    await discount_service.increment_usage_count(
                        validation["discount_id"], session
                    )
        except Exception:
            pass

        # Create order
        # Enforce plan quota: orders_per_month — block creation if the
        # tenant has exhausted their plan's monthly order limit. Without
        # this check the platform would happily create orders that the
        # plan does not allow (and break billing integrity).
        from apps.api.core.feature_flags import check_quota as _check_quota

        quota = await _check_quota(checkout.tenant_id, session, "orders_per_month")
        if not quota.get("allowed", True):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=402,
                detail="Order quota exceeded for current billing period",
            )

        order = Order(
            tenant_id=checkout.tenant_id,
            customer_id=checkout.customer_id,
            checkout_id=checkout.id,
            status=OrderStatus.CONFIRMED,
            total_cents=checkout.total_cents,
            currency=checkout.currency,
            shipping_address_json=checkout.attribution_json.get("shipping_address", {}),
            billing_address_json=checkout.attribution_json.get("billing_address", {}),
        )
        session.add(order)
        await session.flush()

        # Update payment with order_id
        payment.order_id = order.id

        # Create order items from checkout items
        result = await session.execute(
            select(CheckoutItem).where(CheckoutItem.checkout_id == checkout_id)
        )
        checkout_items = list(result.scalars().all())

        from infalette_database.models.order_item import OrderItem
        for ci in checkout_items:
            snapshot = ci.product_snapshot_json or {}
            order_item = OrderItem(
                order_id=order.id,
                product_id=ci.product_id,
                variant_id=ci.variant_id,
                quantity=ci.quantity,
                price_cents=ci.price_cents,
                product_snapshot_json=ci.product_snapshot_json,
                # Immutable tax snapshot (spec §7): frozen at checkout time.
                tax_cents=snapshot.get("tax_cents"),
                tax_rate_bps=snapshot.get("tax_rate_bps"),
            )
            session.add(order_item)

        # Record order created event
        await record_event(
            tenant_id=checkout.tenant_id,
            actor_id=checkout.customer_id,
            event_type="order.created",
            payload={"order_id": str(order.id), "total_cents": checkout.total_cents},
            session=session,
        )

        return order

    async def get_payment_status(
        self,
        tenant_id: UUID,
        checkout_id: UUID,
        session: AsyncSession,
    ) -> dict:
        """Get payment status for a checkout."""
        result = await session.execute(
            select(Payment).where(
                Payment.order_id.in_(
                    select(Order.id).where(Order.checkout_id == checkout_id)
                )
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"status": "pending", "message": "No payment found"}

        return {
            "status": payment.status.value,
            "provider": payment.provider.value,
            "amount_cents": payment.amount_cents,
            "currency": payment.currency,
        }

    async def cancel_checkout(
        self,
        tenant_id: UUID,
        checkout_id: UUID,
        session: AsyncSession,
    ) -> None:
        """Cancel a checkout and release inventory."""
        result = await session.execute(
            select(Checkout).where(
                Checkout.id == checkout_id,
                Checkout.tenant_id == tenant_id,
            )
        )
        checkout = result.scalar_one_or_none()
        if not checkout:
            raise ValueError("Checkout not found")

        # Release inventory for each checkout item
        result = await session.execute(
            select(CheckoutItem).where(CheckoutItem.checkout_id == checkout_id)
        )
        checkout_items = list(result.scalars().all())

        for ci in checkout_items:
            await release_inventory(ci.product_id, ci.quantity, session)

        # Update checkout status
        await session.execute(
            update(Checkout)
            .where(Checkout.id == checkout_id)
            .values(status=CheckoutStatus.CANCELLED)
            .execution_options(synchronize_session="fetch")
        )

        await session.commit()
