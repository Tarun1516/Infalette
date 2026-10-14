"""Custom validation functions."""

from __future__ import annotations

import re
from typing import Optional


def validate_price_cents(value: int) -> int:
    """Validate that price is a non-negative integer in minor units."""
    if not isinstance(value, int):
        raise ValueError("Price must be an integer")
    if value < 0:
        raise ValueError("Price cannot be negative")
    return value


def validate_sku(value: str) -> str:
    """Validate SKU format."""
    if not value or not isinstance(value, str):
        raise ValueError("SKU must be a non-empty string")
    if len(value) > 100:
        raise ValueError("SKU must be 100 characters or less")
    return value.strip()


def validate_slug(value: str) -> str:
    """Validate URL slug format."""
    if not value or not isinstance(value, str):
        raise ValueError("Slug must be a non-empty string")
    if len(value) > 255:
        raise ValueError("Slug must be 255 characters or less")
    if not re.match(r"^[a-z0-9-]+$", value):
        raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
    return value


def validate_phone(value: str) -> str:
    """Validate phone number format."""
    if not value or not isinstance(value, str):
        raise ValueError("Phone must be a non-empty string")
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", value)
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone number must be 10-15 digits")
    return digits


def validate_email(value: str) -> str:
    """Validate email format."""
    if not value or not isinstance(value, str):
        raise ValueError("Email must be a non-empty string")
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, value):
        raise ValueError("Invalid email format")
    return value.lower().strip()
