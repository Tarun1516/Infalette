"""Price calculation with discounts, taxes."""

from __future__ import annotations
from typing import Optional


def calculate_price(price_cents: int, quantity: int) -> int:
    """Calculate price for a given quantity."""
    return price_cents * quantity


def apply_discount(price_cents: int, discount_percent: int) -> int:
    """Apply a percentage discount."""
    return price_cents - (price_cents * discount_percent // 100)


def calculate_total(items: list[dict], discounts: list[dict] = None) -> int:
    """Calculate cart total with discounts.

    Supports both dict items (price_cents/quantity keys) and ORM objects with attributes.
    """
    total = 0
    for item in items:
        if isinstance(item, dict):
            price = item.get("price_cents", 0) or 0
            qty = item.get("quantity", 0) or 0
        else:
            # ORM object fallback
            price = getattr(item, "price_cents", 0) or 0
            qty = getattr(item, "quantity", 0) or 0
        total += int(price) * int(qty)
    for discount in discounts or []:
        total = apply_discount(total, discount.get("percent", 0))
    return max(total, 0)


def calculate_tax(amount_cents: int, tax_rate: float) -> int:
    """Calculate tax amount."""
    return int(amount_cents * tax_rate)
