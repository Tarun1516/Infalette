"""Webhook delivery model."""

from __future__ import annotations

from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class WebhookDelivery(Base):
    """Record of a single outbound webhook delivery attempt."""

    __tablename__ = "webhook_deliveries"

    # Service-facing FK to webhooks.id (legacy `webhook_id` column kept for
    # backwards compatibility with pre-007 rows).
    endpoint_id = Column(
        UUID(as_uuid=True), ForeignKey("webhooks.id"), nullable=True, index=True
    )
    webhook_id = Column(
        UUID(as_uuid=True), ForeignKey("webhooks.id"), nullable=True, index=True
    )
    event_type = Column(String(100), nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(50), default="pending", nullable=False)
    response_status = Column(Integer, nullable=True)
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
