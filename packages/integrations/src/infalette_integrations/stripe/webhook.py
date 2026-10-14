"""Stripe webhook handler."""

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


class StripeWebhookHandler:
    """Handles Stripe webhook events."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._webhook_secret = self._settings.payments.stripe_webhook_secret

    async def verify_webhook_signature(
        self,
        payload,
        signature: str,
    ) -> bool:
        """Verify the webhook signature from Stripe.

        Stripe signs ``f"{timestamp}.{raw_payload}"`` with HMAC-SHA256;
        timestamp and signature come from the ``Stripe-Signature`` header
        (``t=...,v1=...``). Falls back to legacy behavior when the
        header cannot be parsed.
        """
        if not self._webhook_secret:
            if not allow_unverified_webhooks():
                return False
            return True

        try:
            if isinstance(signature, str) and "v1=" in signature and "t=" in signature:
                parts = {}
                for chunk in signature.split(","):
                    key, _, value = chunk.strip().partition("=")
                    parts[key] = value
                timestamp = parts.get("t", "")
                v1 = parts.get("v1", "")
                if timestamp and v1:
                    raw = payload.decode("utf-8", "replace") if isinstance(payload, (bytes, bytearray)) else (
                        payload if isinstance(payload, str) else json.dumps(payload)
                    )
                    expected = hmac.new(
                        self._webhook_secret.encode(),
                        f"{timestamp}.{raw}".encode(),
                        hashlib.sha256,
                    ).hexdigest()
                    return hmac.compare_digest(expected, v1)
        except Exception:
            pass

        # Legacy fallback
        expected = hmac.new(
            self._webhook_secret.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_payment_webhook(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Process a payment webhook from Stripe."""
        event_type = payload.get("type")
        data_object = payload.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            return await self._handle_checkout_session_completed(data_object, session)
        elif event_type == "payment_intent.succeeded":
            return await self._handle_payment_intent_succeeded(data_object, session)
        elif event_type == "payment_intent.payment_failed":
            return await self._handle_payment_intent_failed(data_object, session)
        else:
            return {"status": "ignored", "event_type": event_type}

    async def _handle_checkout_session_completed(
        self,
        session_data: dict,
        session: AsyncSession,
    ) -> dict:
        """Handle checkout.session.completed webhook."""
        payment_intent = session_data.get("payment_intent", "")
        checkout_id_str = session_data.get("metadata", {}).get("checkout_id", "")

        if not checkout_id_str:
            return {"status": "error", "error": "No checkout_id in webhook"}

        from uuid import UUID as UUIDType
        checkout_id = UUIDType(checkout_id_str)

        # Find payment
        result = await session.execute(
            select(Payment).where(
                Payment.provider_payment_id == payment_intent,
                Payment.provider == "stripe",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"status": "error", "error": "Payment not found"}

        payment.status = PaymentStatus.SUCCEEDED

        # Find checkout and create order
        result = await session.execute(
            select(Checkout).where(Checkout.id == checkout_id)
        )
        checkout = result.scalar_one_or_none()
        if checkout:
            from sqlalchemy import update
            await session.execute(
                update(Checkout)
                .where(Checkout.id == checkout_id)
                .values(status=CheckoutStatus.PAID)
                .execution_options(synchronize_session="fetch")
            )

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

            payment.order_id = order.id

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
            "event_type": "checkout.session.completed",
            "payment_id": payment_intent,
            "payment_status": payment.status.value,
        }

    async def _handle_payment_intent_succeeded(
        self,
        payment_intent_data: dict,
        session: AsyncSession,
    ) -> dict:
        """Handle payment_intent.succeeded webhook."""
        payment_intent = payment_intent_data.get("id", "")

        result = await session.execute(
            select(Payment).where(
                Payment.provider_payment_id == payment_intent,
                Payment.provider == "stripe",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"status": "error", "error": "Payment not found"}

        payment.status = PaymentStatus.SUCCEEDED
        await session.commit()

        return {
            "status": "processed",
            "event_type": "payment_intent.succeeded",
            "payment_id": payment_intent,
        }

    async def _handle_payment_intent_failed(
        self,
        payment_intent_data: dict,
        session: AsyncSession,
    ) -> dict:
        """Handle payment_intent.payment_failed webhook."""
        payment_intent = payment_intent_data.get("id", "")

        result = await session.execute(
            select(Payment).where(
                Payment.provider_payment_id == payment_intent,
                Payment.provider == "stripe",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"status": "error", "error": "Payment not found"}

        payment.status = PaymentStatus.FAILED
        await session.commit()

        # Send notification
        await self._send_notification_on_failure(payment, session)

        return {
            "status": "processed",
            "event_type": "payment_intent.payment_failed",
            "payment_id": payment_intent,
        }

    async def _send_notification_on_failure(
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

    async def handle_connect_webhooks(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Handle Stripe Connect webhooks."""
        event_type = payload.get("type")

        if event_type == "account.updated":
            return {"status": "processed", "event_type": "account.updated"}
        elif event_type == "transfer.created":
            return {"status": "processed", "event_type": "transfer.created"}
        else:
            return {"status": "ignored", "event_type": event_type}
