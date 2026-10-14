"""Conversation management services.

Uses the single ``Message`` model (the same table social webhook
handlers write to) so the unified inbox shows the full thread across
Instagram, WhatsApp and website — not two divergent stores.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.conversation import (
    Conversation,
    ConversationChannel,
)
from infalette_database.models.message import Message, MessageDirection


def _normalize_channel(value) -> ConversationChannel:
    """Map loose channel strings ("web", "site") onto the enum."""
    if isinstance(value, ConversationChannel):
        return value
    raw = str(value or "website").strip().lower()
    aliases = {"web": "website", "site": "website", "ig": "instagram"}
    raw = aliases.get(raw, raw)
    try:
        return ConversationChannel(raw)
    except ValueError:
        return ConversationChannel.WEBSITE


async def list_conversations(
    tenant_id: UUID,
    session: AsyncSession,
    status: Optional[str] = None,
    channel: Optional[str] = None,
) -> list[Conversation]:
    """List conversations for a tenant."""
    query = select(Conversation).where(Conversation.tenant_id == tenant_id)
    if status:
        query = query.where(Conversation.status == status)
    if channel:
        query = query.where(Conversation.channel == _normalize_channel(channel))
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_conversation(
    tenant_id: UUID,
    conversation_id: UUID,
    session: AsyncSession,
) -> Conversation | None:
    """Get a conversation by ID."""
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_conversation(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Conversation:
    """Create a new conversation."""
    conversation = Conversation(
        tenant_id=tenant_id,
        customer_id=data.get("customer_id"),
        channel=_normalize_channel(data.get("channel")),
        status=data.get("status", "active"),
        assigned_to=data.get("assigned_to"),
        metadata_json=data.get("metadata_json") or data.get("metadata") or {},
        lead_id=data.get("lead_id"),
        customer_name=data.get("customer_name"),
        external_id=data.get("external_id"),
        participants_json=data.get("participants_json", []),
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def send_message(
    tenant_id: UUID,
    conversation_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Message:
    """Send a message in a conversation (stored in the shared messages table)."""
    conversation = await get_conversation(tenant_id, conversation_id, session)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    sender_type = data.get("sender_type", "agent")
    direction = (
        MessageDirection.INBOUND if sender_type == "customer" else MessageDirection.OUTBOUND
    )
    message = Message(
        conversation_id=conversation_id,
        sender_id=data.get("sender_id"),
        direction=direction.value if hasattr(direction, "value") else direction,
        content=data.get("content"),
        external_id=data.get("external_id"),
        attachments_json=data.get("attachments_json", []),
        status=data.get("status", "sent"),
    )
    session.add(message)

    # Touch the conversation so recency ordering reflects this message
    import datetime

    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .values(updated_at=datetime.datetime.utcnow())
        .execution_options(synchronize_session="fetch")
    )

    await session.commit()
    await session.refresh(message)
    return message


async def get_conversation_messages(
    tenant_id: UUID,
    conversation_id: UUID,
    session: AsyncSession,
) -> list[Message]:
    """Get all messages for a conversation, oldest first."""
    conversation = await get_conversation(tenant_id, conversation_id, session)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
    )
    return list(result.scalars().all())


async def assign_conversation(
    tenant_id: UUID,
    conversation_id: UUID,
    agent_id: UUID,
    session: AsyncSession,
) -> Conversation | None:
    """Assign a conversation to an agent."""
    conversation = await get_conversation(tenant_id, conversation_id, session)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .values(assigned_to=agent_id, status="active")
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_conversation(tenant_id, conversation_id, session)


async def close_conversation(
    tenant_id: UUID,
    conversation_id: UUID,
    session: AsyncSession,
) -> Conversation | None:
    """Close a conversation."""
    conversation = await get_conversation(tenant_id, conversation_id, session)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        .values(status="closed")
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_conversation(tenant_id, conversation_id, session)
