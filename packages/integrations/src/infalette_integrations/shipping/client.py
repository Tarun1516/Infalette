"""Shipping provider client."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

import httpx

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class ShippingProviderClient:
    """Client for shipping providers (DTDC, Delhivery, Blue Dart, Ecom Express)."""

    PROVIDERS = {
        "dtdc": {"name": "DTDC", "base_url": "https://api.dtdc.com"},
        "delhivery": {"name": "Delhivery", "base_url": "https://api.delhivery.com"},
        "bluedart": {"name": "Blue Dart", "base_url": "https://api.bluedart.com"},
        "ecom": {"name": "Ecom Express", "base_url": "https://api.ecomexpress.in"},
    }

    def __init__(self) -> None:
        self._settings = get_settings()

    def _auth_header(self) -> str:
        """Authorization header with the real secret (SecretStr-safe)."""
        api_key = self._settings.shipping.api_key
        value = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else str(api_key)
        return f"Bearer {value}"

    async def get_shipping_options(
        self,
        provider: str,
        origin_pin: str,
        destination_pin: str,
        weight_kg: float,
        length: float = 0,
        width: float = 0,
        height: float = 0,
        api_key: Optional[str] = None,
        declared_value_cents: int = 0,
        cod: bool = False,
    ) -> list[dict]:
        """Get live shipping options (rates) from a carrier.

        ``api_key`` overrides the platform-level key so tenants can use
        their own carrier account (spec: each influencer connects their
        own shipping/payment accounts). Falls back to the global key.
        """
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        auth = (
            f"Bearer {api_key}"
            if api_key
            else self._auth_header()
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{provider_info['base_url']}/v1/rates",
                json={
                    "origin_pincode": origin_pin,
                    "destination_pincode": destination_pin,
                    "weight": weight_kg,
                    "length": length,
                    "width": width,
                    "height": height,
                    "declared_value_cents": declared_value_cents,
                    "cod": cod,
                },
                headers={"Authorization": auth},
            )
            response.raise_for_status()
            data = response.json()

        return data.get("rates", [])

    async def create_shipment(
        self,
        provider: str,
        shipment_data: dict,
    ) -> dict:
        """Create a shipment with a provider."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{provider_info['base_url']}/v1/shipments",
                json=shipment_data,
                headers={"Authorization": self._auth_header()},
            )
            response.raise_for_status()
            return response.json()

    async def get_tracking_status(
        self,
        provider: str,
        tracking_number: str,
    ) -> dict:
        """Get tracking status for a shipment."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{provider_info['base_url']}/v1/tracking/{tracking_number}",
                headers={"Authorization": self._auth_header()},
            )
            response.raise_for_status()
            return response.json()

    async def cancel_shipment(
        self,
        provider: str,
        shipment_id: str,
    ) -> dict:
        """Cancel a shipment."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{provider_info['base_url']}/v1/shipments/{shipment_id}",
                headers={"Authorization": self._auth_header()},
            )
            response.raise_for_status()
            return response.json()

    async def handle_provider_webhooks(
        self,
        provider: str,
        payload: dict,
    ) -> dict:
        """Handle webhook events from shipping providers."""
        event_type = payload.get("event_type", "")
        tracking_number = payload.get("tracking_number", "")
        status = payload.get("status", "")

        logger.info(f"Shipping webhook: provider={provider}, event={event_type}, tracking={tracking_number}, status={status}")

        return {
            "status": "processed",
            "provider": provider,
            "event_type": event_type,
            "tracking_number": tracking_number,
            "shipment_status": status,
        }


# Compatibility alias
ShippingClient = ShippingProviderClient
