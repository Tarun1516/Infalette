"""Razorpay webhook handler."""

from __future__ import annotations

import hmac
import hashlib
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.payment import Payment, PaymentStatus
from infalette_database.models.order import Order, OrderStatus
from infalette_database.models.checkout import Checkout, CheckoutStatus
from infalette_analytics.event_bus import record_event
from infalette_config import get_settings
from infalette_integrations.base import allow_unverified_webhooks


def canonical_body(payload) -> bytes:
    """Razorpay signs the exact bytes received. Accept raw body when available."""
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode()
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class RazorpayWebhookHandler:
    """Handles Razorpay webhook events."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._webhook_secret = self._settings.payments.razorpay_webhook_secret

    async def verify_webhook_signature(
        self,
        payload,
        signature: str,
    ) -> bool:
        """Verify the webhook signature from Razorpay."""
        if not self._webhook_secret:
            if not allow_unverified_webhooks():
                return False
            return True

        expected = hmac.new(
            self._webhook_secret.encode(),
            canonical_body(payload),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_payment_webhook(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Process a payment webhook from Razorpay."""
        event_type = payload.get("event")
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

        payment_id = payment_entity.get("id", "")
        checkout_id_str = payment_entity.get("notes", {}).get("checkout_id", "")
        status = payment_entity.get("status", "")

        if not checkout_id_str:
            return {"status": "error", "error": "No checkout_id in webhook"}

        from uuid import UUID as UUIDType
        checkout_id = UUIDType(checkout_id_str)

        # Find payment
        result = await session.execute(
            select(Payment).where(
                Payment.provider_payment_id == payment_id,
                Payment.provider == "razorpay",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"status": "error", "error": "Payment not found"}

        # Update payment status
        if status in ("captured", "succeeded", "paid"):
            payment.status = PaymentStatus.SUCCEEDED
        elif status in ("failed", "denied"):
            payment.status = PaymentStatus.FAILED
        else:
            return {"status": "ignored", "event_type": event_type}

        # If payment succeeded, create order
        if payment.status == PaymentStatus.SUCCEEDED:
            # Find checkout
            result = await session.execute(
                select(Checkout).where(Checkout.id == checkout_id)
            )
            checkout = result.scalar_one_or_none()
            if checkout:
                # Update checkout status
                from sqlalchemy import update
                await session.execute(
                    update(Checkout)
                    .where(Checkout.id == checkout_id)
                    .values(status=CheckoutStatus.PAID)
                    .execution_options(synchronize_session="fetch")
                )

                # Create order
                from infalette_database.models.order import Order, OrderStatus
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

                # Record event
                await record_event(
                    tenant_id=checkout.tenant_id,
                    actor_id=checkout.customer_id,
                    event_type="payment.succeeded",
                    payload={"payment_id": str(payment.id), "order_id": str(order.id)},
                    session=session,
                )

        await session.commit()

        return {
            "status": "processed",
            "event_type": event_type,
            "payment_id": payment_id,
            "payment_status": payment.status.value,
        }

    async def update_payment_status(
        self,
        payment_id: str,
        status: str,
        session: AsyncSession,
    ) -> bool:
        """Update payment status."""
        result = await session.execute(
            select(Payment).where(
                Payment.provider_payment_id == payment_id,
                Payment.provider == "razorpay",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return False

        if status in ("captured", "succeeded", "paid"):
            payment.status = PaymentStatus.SUCCEEDED
        elif status in ("failed", "denied"):
            payment.status = PaymentStatus.FAILED

        await session.commit()
        return True

    async def create_order_from_payment(
        self,
        payment: Payment,
        checkout: Checkout,
        session: AsyncSession,
    ) -> Order:
        """Create an order from a confirmed payment and checkout."""
        from infalette_database.models.order import Order, OrderStatus
        from infalette_database.models.order_item import OrderItem
        from infalette_database.models.checkout_item import CheckoutItem

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

        # Create order items
        result = await session.execute(
            select(CheckoutItem).where(CheckoutItem.checkout_id == checkout.id)
        )
        checkout_items = list(result.scalars().all())

        for ci in checkout_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=ci.product_id,
                variant_id=ci.variant_id,
                quantity=ci.quantity,
                price_cents=ci.price_cents,
                product_snapshot_json=ci.product_snapshot_json,
            )
            session.add(order_item)

        await session.commit()
        await session.refresh(order)
        return order

    async def send_notification_on_failure(
        self,
        payment: Payment,
        session: AsyncSession,
    ) -> None:
        """Send a notification when a payment fails."""
        from infalette_integrations.email.client import EmailClient
        from infalette_database.models.customer import Customer

        result = await session.execute(
            select(Customer).where(Customer.id == payment.order_id)
        )
        customer = result.scalar_one_or_none()

        if customer and customer.email:
            email_client = EmailClient()
            await email_client.send_email(
                to=customer.email,
                subject="Payment Failed",
                html_content="<p>Your payment was not processed. Please try again.</p>",
                tenant_id=payment.tenant_id,
            )
