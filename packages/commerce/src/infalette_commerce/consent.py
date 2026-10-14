"""Consent gating for outbound follow-ups (spec §3 CRM + §9 DPDP).

"Follow-up happens only where channel rules and consent permit it."
Every outbound marketing touch (abandoned-cart recovery, automation
messages) must pass :func:`can_contact` before sending.
"""

from __future__ import annotations

from typing import Optional

# Channels that require explicit opt-in
CONSENT_CHANNELS = ("email", "whatsapp", "sms", "instagram")


def can_contact(consent_json: Optional[dict], channel: str) -> bool:
    """Return True only when the customer consented to this channel.

    Consent shape (customers.consent_json):
        {"email": true, "whatsapp": true, "sms": false,
         "marketing": true, "updated_at": "..."}
    Rules:
    - Missing/empty consent -> not permitted (opt-in, never opt-out).
    - Channel key must be explicitly True.
    - If a ``marketing`` key exists and is False, nothing is permitted.
    """
    if not consent_json or not isinstance(consent_json, dict):
        return False
    if consent_json.get("marketing") is False:
        return False
    return bool(consent_json.get(channel) is True)


def customer_can_contact(customer, channel: str) -> bool:
    """Convenience wrapper reading consent_json off an ORM customer."""
    return can_contact(getattr(customer, "consent_json", None), channel)
