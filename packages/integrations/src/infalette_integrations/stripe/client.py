"""Stripe payment integration client."""

from __future__ import annotations

import hmac
import hashlib
import json
from typing import Optional
from uuid import UUID

import httpx

from infalette_config import get_settings
from infalette_integrations.base import allow_unverified_webhooks, allow_dummy_payments


class StripeClient:
    """Client for interacting with the Stripe API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._secret_key = self._settings.payments.stripe_secret_key
        self._webhook_secret = self._settings.payments.stripe_webhook_secret
        self._base_url = "https://api.stripe.com/v1"

    async def create_checkout_session(
        self,
        checkout,
        tenant_id: UUID,
        stripe_account_id: Optional[str] = None,
    ) -> dict:
        """Create a Stripe Checkout Session.

        When ``stripe_account_id`` is set (Stripe Connect), the payment
        is routed to the tenant's connected account via transfer_data.
        """
        amount = checkout.total_cents
        currency = checkout.currency

        payload = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price_data": {
                    "currency": currency,
                    "product_data": {
                        "name": f"Order for tenant {tenant_id}",
                    },
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            "mode": "payment",
            "metadata": {
                "checkout_id": str(checkout.id),
                "tenant_id": str(tenant_id),
            },
            "success_url": f"{self._settings.storefront_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{self._settings.storefront_url}/checkout/cancel",
        }

        if stripe_account_id:
            payload["transfer_data"] = {"destination": stripe_account_id}

        if not self._secret_key:
            if not allow_dummy_payments():
                raise ValueError("Stripe secret_key not configured")
            return {"id": "cs_dummy", "url": "https://example.com/pay", "payment_intent": "pi_dummy"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/checkout/sessions",
                json=payload,
                headers={"Authorization": f"Bearer {self._secret_key.get_secret_value()}"},
            )
            response.raise_for_status()
            return response.json()

    async def verify_payment(self, payment_intent_id: str) -> dict:
        """Verify a payment intent's status."""
        if not self._secret_key:
            if not allow_dummy_payments():
                raise ValueError("Stripe secret_key not configured")
            return {"status": "succeeded", "id": payment_intent_id}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/payment_intents/{payment_intent_id}",
                headers={"Authorization": f"Bearer {self._secret_key.get_secret_value()}"},
            )
            response.raise_for_status()
            return response.json()

    async def create_refund(
        self,
        payment_intent_id: str,
        amount_cents: int,
        reason: Optional[str] = None,
    ) -> dict:
        """Create a refund for a payment intent."""
        payload = {
            "payment_intent": payment_intent_id,
            "amount": amount_cents,
        }
        if reason:
            payload["metadata"] = {"reason": reason}

        if not self._secret_key:
            if not allow_dummy_payments():
                raise ValueError("Stripe secret_key not configured")
            return {"id": "re_dummy", "status": "succeeded"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/refunds",
                json=payload,
                headers={"Authorization": f"Bearer {self._secret_key.get_secret_value()}"},
            )
            response.raise_for_status()
            return response.json()

    async def verify_webhook_signature(
        self,
        payload,
        signature: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verify the webhook signature from Stripe.

        Stripe signs ``f"{timestamp}.{raw_payload}"`` with HMAC-SHA256;
        the timestamp (``t``) and signature (``v1``) come from the
        ``Stripe-Signature`` header. Signatures older than
        ``tolerance_seconds`` (default 5 minutes) are rejected to prevent
        replay attacks. Falls back to legacy direct-compare
        behavior when the header cannot be parsed.
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
                    # Replay protection: reject stale timestamps.
                    try:
                        import time as _time

                        age = abs(_time.time() - int(timestamp))
                        if age > tolerance_seconds:
                            return False
                    except (TypeError, ValueError):
                        return False
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

        # Legacy fallback: direct comparison over a dict payload
        try:
            expected = hmac.new(
                self._webhook_secret.encode(),
                str(payload).encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    async def create_connect_account(self, tenant_id: UUID) -> dict:
        """Create a Stripe Connect account for a tenant."""
        if not self._secret_key:
            if not allow_dummy_payments():
                raise ValueError("Stripe secret_key not configured")
            return {"id": "acct_dummy"}

        payload = {
            "type": "express",
            "country": "IN",
            "email": f"tenant-{tenant_id}@infalette.com",
            "capabilities": {
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/accounts",
                json=payload,
                headers={"Authorization": f"Bearer {self._secret_key.get_secret_value()}"},
            )
            response.raise_for_status()
            return response.json()
