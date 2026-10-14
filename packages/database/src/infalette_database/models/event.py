"""Event model."""

from __future__ import annotations

from sqlalchemy import Column, String, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import synonym

from infalette_database.base import Base, TenantMixin


class Event(Base, TenantMixin):
    """Event model.

    Domain events that drive notifications, CRM timelines,
    analytics and automation without tightly coupling every module.

    Useful domain events include:
    - tenant.created
    - storefront.published
    - product.updated
    - inventory.changed
    - cart.abandoned
    - checkout.created
    - payment.succeeded
    - payment.failed
    - order.fulfilled
    - message.received
    - comment.received
    - automation.triggered
    - lead.stage_changed
    - customer.consent_changed

    Alembic column is event_type; `type` is kept as synonym for
    backwards compatibility with legacy code that used Event.type.
    """

    __tablename__ = "events"

    actor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    event_type = Column(String(100), nullable=False, index=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    request_id = Column(String(255), nullable=True, index=True)

    # Synonym so both Event.event_type and Event.type refer to same column
    type = synonym("event_type")

    # ------------------------------------------------------------------
    # Additional aliases for payload variations found in legacy code
    # ------------------------------------------------------------------
    @property
    def payload(self) -> dict:  # pragma: no cover - legacy shim
        return self.payload_json

    @payload.setter
    def payload(self, val: dict) -> None:  # pragma: no cover
        self.payload_json = val or {}
