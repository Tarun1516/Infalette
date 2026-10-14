"""Razorpay payment integration client."""

from __future__ import annotations

import hmac
import hashlib
from typing import Optional
from uuid import UUID

import httpx

from infalette_config import get_settings
from infalette_integrations.base import allow_unverified_webhooks, allow_dummy_payments
from infalette_integrations.razorpay.webhook import canonical_body


class RazorpayClient:
    """Client for interacting with the Razorpay API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._key_id = self._settings.payments.razorpay_key_id
        self._key_secret = self._settings.payments.razorpay_key_secret
        self._webhook_secret = self._settings.payments.razorpay_webhook_secret
        self._base_url = "https://api.razorpay.com/v1"

    async def create_payment_link(
        self,
        checkout,
        tenant_id: UUID,
        linked_account_id: Optional[str] = None,
    ) -> dict:
        """Create a payment link via Razorpay.

        When ``linked_account_id`` is set, funds are routed to the
        tenant's linked merchant account via a Razorpay Route transfer.
        """
        amount = checkout.total_cents
        currency = checkout.currency

        payload = {
            "amount": amount,
            "currency": currency,
            "accept_partial": False,
            "description": f"Order for tenant {tenant_id}",
            "notes": {
                "checkout_id": str(checkout.id),
                "tenant_id": str(tenant_id),
            },
            "callback_url": f"{self._settings.api_url}/api/v1/webhooks/razorpay",
            "callback_method": "post",
        }

        if linked_account_id:
            payload["transfers"] = [
                {
                    "account": linked_account_id,
                    "amount": checkout.total_cents,
                    "currency": checkout.currency,
                    "notes": {"checkout_id": str(checkout.id)},
                }
            ]
            # Razorpay places transfer notes separately; the top-level
            # notes.checkout_id above is what webhook extraction relies on.

        if not self._key_id or not self._key_secret:
            if not allow_dummy_payments():
                raise ValueError("Razorpay key_id/key_secret not configured")
            return {"id": "dummy_payment_id", "short_url": "https://example.com/pay"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/payment_links",
                json=payload,
                auth=(self._key_id, self._key_secret.get_secret_value() if self._key_secret else ""),
            )
            response.raise_for_status()
            return response.json()

    async def verify_payment(self, payment_id: str) -> dict:
        """Verify a payment's status."""
        if not self._key_id or not self._key_secret:
            # Never fabricate a "captured" result with unconfigured keys:
            # reconciliation would mark unpaid orders as paid.
            if not allow_dummy_payments():
                raise ValueError("Razorpay key_id/key_secret not configured")
            return {"status": "captured", "id": payment_id}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/payments/{payment_id}",
                auth=(self._key_id, self._key_secret.get_secret_value() if self._key_secret else ""),
            )
            response.raise_for_status()
            return response.json()

    async def create_refund(
        self,
        payment_id: str,
        amount_cents: int,
        reason: Optional[str] = None,
    ) -> dict:
        """Create a refund for a payment."""
        payload = {"amount": amount_cents}
        if reason:
            payload["notes"] = {"reason": reason}

        if not self._key_id or not self._key_secret:
            if not allow_dummy_payments():
                raise ValueError("Razorpay key_id/key_secret not configured")
            return {"id": "dummy_refund_id", "status": "processed"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/payments/{payment_id}/refund",
                json=payload,
                auth=(self._key_id, self._key_secret.get_secret_value() if self._key_secret else ""),
            )
            response.raise_for_status()
            return response.json()

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

        # Razorpay uses SHA256 HMAC over the exact raw body bytes
        expected = hmac.new(
            self._webhook_secret.encode(),
            canonical_body(payload),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def get_payment_link(self, link_id: str) -> dict:
        """Get a payment link by ID."""
        if not self._key_id or not self._key_secret:
            if not allow_dummy_payments():
                raise ValueError("Razorpay key_id/key_secret not configured")
            return {"id": link_id, "status": "captured"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/payment_links/{link_id}",
                auth=(self._key_id, self._key_secret.get_secret_value() if self._key_secret else ""),
            )
            response.raise_for_status()
            return response.json()
