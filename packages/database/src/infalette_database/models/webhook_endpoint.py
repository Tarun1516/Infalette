"""Webhook endpoint model."""

from __future__ import annotations

from sqlalchemy import Column, String, JSON

from infalette_database.base import Base, TenantMixin


class WebhookEndpoint(Base, TenantMixin):
    """Outbound webhook endpoint registered by a tenant.

    When subscribed events occur, the platform POSTs an HMAC-signed
    payload to ``url`` using ``secret``.
    """

    __tablename__ = "webhooks"

    name = Column(String(255), nullable=False, default="")
    url = Column(String(500), nullable=False)
    events = Column(JSON, nullable=False, default=list)
    status = Column(String(50), default="active", nullable=False)
    secret = Column(String(255), nullable=True)
