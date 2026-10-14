"""Message model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class MessageDirection(str, enum.Enum):
    """Direction of a message within a conversation."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Message(Base):
    """Message model.

    Individual messages within a conversation.
    """

    __tablename__ = "messages"

    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    sender_id = Column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    direction = Column(String(50), default=MessageDirection.INBOUND.value, nullable=False)
    content = Column(Text, nullable=False)
    # Provider-side message id used for webhook deduplication
    external_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="sent", nullable=False)
    attachments_json = Column(JSON, nullable=False, default=list)
