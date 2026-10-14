"""Conversation model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class ConversationChannel(str, enum.Enum):
    """Conversation channel enum."""

    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"


class Conversation(Base, TenantMixin):
    """Conversation model.

    Normalized conversation model for all channels (Instagram, WhatsApp, website).
    """

    __tablename__ = "conversations"

    channel = Column(
        SAEnum(ConversationChannel, native_enum=False, length=50), nullable=False, index=True
    )
    # Provider-side conversation id (e.g. IG media id or `dm_{username}`)
    external_id = Column(String(255), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    status = Column(String(50), default="active", nullable=False)
    participants_json = Column(JSON, nullable=False, default=list)
    lead_id = Column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True, index=True
    )
    assigned_to = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    metadata_json = Column(JSON, nullable=False, default=dict)
