"""Shipping calculation service."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ShippingService:
    """Shipping calculation and management.

    Rates are configurable per tenant through ``Store.shipping_rules_json``:
    ``{
        "free_shipping_threshold_cents": 100000,
        "weight_surcharge_above_kg": 2.0,
        "surcharge_cents_per_kg": 500,
        "rates": {
            "standard": {"price_cents": 10000, "estimated_days": 3,
                          "carrier": "DTDC",
                          "zone_prices_cents": {"MH": 8000}}
        }
    }``
    Missing keys fall back to the built-in defaults below.
    """

    SHIPPING_RATES = {
        "standard": {"price_cents": 10000, "estimated_days": 3, "carrier": "DTDC"},
        "express": {"price_cents": 20000, "estimated_days": 1, "carrier": "Bluedart"},
        "same_day": {"price_cents": 50000, "estimated_days": 0, "carrier": "Local"},
    }

    def __init__(self, rules: Optional[dict] = None) -> None:
        self._rules = dict(rules or {})

    def _rate(self, shipping_type: str) -> dict:
        rates = self._rules.get("rates") or {}
        configured = rates.get(shipping_type)
        base = self.SHIPPING_RATES.get(shipping_type, self.SHIPPING_RATES["standard"])
        rate = {**base}
        if isinstance(configured, dict):
            for key in ("price_cents", "estimated_days", "carrier"):
                if configured.get(key) is not None:
                    rate[key] = configured[key]
            zone_prices = configured.get("zone_prices_cents")
            if isinstance(zone_prices, dict):
                rate["_zone_prices"] = zone_prices
        return rate

    def calculate_shipping_cost(
        self,
        zone: str,
        weight_kg: float,
        order_total_cents: int,
        shipping_type: str = "standard",
    ) -> int:
        """Calculate shipping cost based on zone, weight, and order value."""
        rate = self._rate(shipping_type)

        # Free-shipping threshold is tenant-configurable.
        threshold = self._rules.get("free_shipping_threshold_cents")
        threshold = int(threshold) if threshold is not None else 100000
        if order_total_cents >= threshold:
            return 0

        # Zone-specific price overrides win over the flat rate.
        zone_prices = rate.pop("_zone_prices", None) or (self._rules.get("zone_prices_cents") or {}).get(shipping_type)
        if zone is not None and isinstance(zone_prices, dict):
            zone_price = zone_prices.get(str(zone).upper()) or zone_prices.get(str(zone))
            if zone_price is not None:
                base_cost = int(zone_price)
            else:
                base_cost = int(rate["price_cents"])
        else:
            base_cost = int(rate["price_cents"])

        # Weight-based surcharge above the configurable allowance
        surcharge_above = float(self._rules.get("weight_surcharge_above_kg", 2.0))
        per_kg = int(self._rules.get("surcharge_cents_per_kg", 500))
        if weight_kg > surcharge_above:
            base_cost += int((weight_kg - surcharge_above) * per_kg)

        return base_cost

    async def get_shipping_cost(
        self,
        zone: str,
        weight_kg: float,
        order_total_cents: int,
        shipping_type: str = "standard",
        destination_pincode: Optional[str] = None,
        destination_country: str = "India",
        declared_value_cents: int = 0,
        cod: bool = False,
    ) -> dict:
        """Shipping cost preferring **live carrier rates** when configured.

        Tenant ``shipping_rules_json`` may carry a ``carrier`` block::

            "carrier": {"provider": "delhivery", "api_key": "...",
                        "origin_pincode": "560001"}

        When present (and shipping to India), live rates are queried with
        the tenant's own carrier credentials; the cheapest matching service
        wins. Any failure silently falls back to the configured zone/weight
        rules so checkout never blocks on the carrier API.
        """
        carrier_cfg = self._rules.get("carrier") or {}
        if (
            isinstance(carrier_cfg, dict)
            and destination_country.lower() == "india"
            and destination_pincode
            and carrier_cfg.get("provider")
            and carrier_cfg.get("api_key")
        ):
            try:
                from infalette_integrations.shipping.client import (
                    ShippingProviderClient,
                )

                rates = await ShippingProviderClient().get_shipping_options(
                    str(carrier_cfg["provider"]).lower(),
                    origin_pin=str(carrier_cfg.get("origin_pincode", "")),
                    destination_pin=str(destination_pincode),
                    weight_kg=weight_kg,
                    api_key=str(carrier_cfg["api_key"]),
                    declared_value_cents=declared_value_cents,
                    cod=cod,
                )
                usable = [
                    r for r in rates
                    if isinstance(r, dict) and r.get("total_cents") is not None
                ]
                if usable:
                    best = min(usable, key=lambda r: int(r["total_cents"]))
                    return {
                        "price_cents": int(best["total_cents"]),
                        "carrier": best.get("carrier")
                        or carrier_cfg.get("provider"),
                        "estimated_days": best.get("estimated_days"),
                        "live": True,
                    }
            except Exception:
                pass  # fall back to configured rules below

        return {
            "price_cents": self.calculate_shipping_cost(
                zone=zone,
                weight_kg=weight_kg,
                order_total_cents=order_total_cents,
                shipping_type=shipping_type,
            ),
            "carrier": self._rate(shipping_type).get("carrier"),
            "estimated_days": self._rate(shipping_type).get("estimated_days"),
            "live": False,
        }

    def get_shipping_options(
        self,
        zone: str,
        weight_kg: float,
        order_total_cents: int,
    ) -> list[dict]:
        """Get available shipping options."""
        options = []
        for key in self.SHIPPING_RATES.keys():
            rate = self._rate(key)
            cost = self.calculate_shipping_cost(zone, weight_kg, order_total_cents, key)
            options.append({
                "id": key,
                "name": str(rate["carrier"]) + " " + key.title(),
                "price_cents": cost,
                "estimated_days": rate["estimated_days"],
                "carrier": rate["carrier"],
            })
        return options

    def validate_shipping_address(self, address: dict) -> bool:
        """Validate a shipping address."""
        required_fields = ["line1", "city", "state", "postal_code", "country"]
        for field in required_fields:
            if not address.get(field):
                return False
        return True

    async def create_shipment(
        self,
        order_id: UUID,
        shipping_option: str,
        address: dict,
        session: AsyncSession,
        tenant_id: Optional[UUID] = None,
    ) -> dict:
        """Create a shipment with a shipping provider.

        Attempts the live carrier API when the tenant has a connected
        ``shipping`` integration; otherwise records a PENDING fulfillment
        for manual tracking entry.
        """
        from infalette_database.models.fulfillment import Fulfillment, FulfillmentStatus
        from infalette_database.models.order import Order, OrderStatus

        rate = self._rate(shipping_option)
        carrier = str(rate.get("carrier", "Local"))

        tracking_number: Optional[str] = None
        provider_status = None
        try:
            from infalette_database.models.integration import Integration

            row = await session.execute(
                select(Integration).where(
                    Integration.tenant_id == tenant_id,
                    Integration.provider.in_(("shipping", "dtdc", "delhivery", "bluedart")),
                    Integration.status.in_(("connected", "active")),
                )
            )
            integration = row.scalars().first()
            if integration is not None and integration.credentials_json:
                provider = str(integration.provider or "dtdc").lower()
                from infalette_integrations.shipping.client import ShippingProviderClient

                result = await ShippingProviderClient().create_shipment(
                    "dtdc" if provider == "shipping" else provider,
                    {
                        "order_id": str(order_id),
                        "carrier": carrier,
                        "service_type": shipping_option,
                        "ship_to": address,
                    },
                )
                tracking_number = (
                    result.get("tracking_number")
                    or result.get("waybill")
                    or result.get("awb_number")
                )
                provider_status = result.get("status")
        except Exception:
            tracking_number = None  # fall back to manual fulfillment

        fulfillment = Fulfillment(
            order_id=order_id,
            tracking_number=tracking_number,
            carrier=carrier,
            status=(
                FulfillmentStatus.SHIPPED if tracking_number else FulfillmentStatus.PENDING
            ),
        )
        session.add(fulfillment)
        await session.flush()

        await session.execute(
            __import__("sqlalchemy").update(Order)
            .where(Order.id == order_id)
            .values(status=OrderStatus.PROCESSING)
            .execution_options(synchronize_session="fetch")
        )

        await session.commit()
        await session.refresh(fulfillment)

        return {
            "fulfillment_id": str(fulfillment.id),
            "carrier": fulfillment.carrier,
            "tracking_number": fulfillment.tracking_number,
            "status": fulfillment.status.value,
            "provider_status": provider_status,
        }
