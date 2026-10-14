"""Conversation management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import enforce_quota, require_feature, Feature

router = APIRouter(dependencies=[Depends(require_feature(Feature.UNIFIED_INBOX))])


def _serialize_conversation(c) -> dict:
    """ORM -> dict for the inbox list/detail surfaces."""
    channel = getattr(c.channel, "value", c.channel)
    return {
        "id": str(c.id),
        "tenant_id": str(c.tenant_id),
        "channel": channel,
        "external_id": getattr(c, "external_id", None),
        "customer_name": getattr(c, "customer_name", None),
        "customer_id": str(c.customer_id) if getattr(c, "customer_id", None) else None,
        "status": c.status,
        "lead_id": str(c.lead_id) if getattr(c, "lead_id", None) else None,
        "assigned_to": str(c.assigned_to) if getattr(c, "assigned_to", None) else None,
        "metadata_json": getattr(c, "metadata_json", None) or {},
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("/")
async def list_conversations(
    status: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List conversations for the tenant."""
    from apps.api.modules.conversation.services import list_conversations
    convs = await list_conversations(user.tenant_id, session, status, channel)
    return [_serialize_conversation(c) for c in convs]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new conversation."""
    from apps.api.modules.conversation.services import create_conversation
    conv = await create_conversation(user.tenant_id, data, session)
    return _serialize_conversation(conv)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a conversation by ID."""
    from apps.api.modules.conversation.services import get_conversation
    conv = await get_conversation(user.tenant_id, conversation_id, session)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _serialize_conversation(conv)


@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
    quota=Depends(enforce_quota("messages_per_month")),
):
    """Send a message in a conversation (plan quota enforced)."""
    from apps.api.modules.conversation.services import send_message
    msg = await send_message(user.tenant_id, conversation_id, data, session)
    return {
        "id": str(msg.id),
        "conversation_id": str(msg.conversation_id),
        "sender_id": str(msg.sender_id) if msg.sender_id else None,
        "direction": msg.direction,
        "content": msg.content,
        "status": msg.status,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get all messages for a conversation (full thread across channels)."""
    from apps.api.modules.conversation.services import get_conversation_messages
    msgs = await get_conversation_messages(user.tenant_id, conversation_id, session)
    return [
        {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "sender_id": str(m.sender_id) if m.sender_id else None,
            "direction": m.direction,
            "content": m.content,
            "external_id": m.external_id,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


class AssignRequest(BaseModel):
    """Assignment payload; accepts either key from different clients."""

    user_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None


@router.post("/{conversation_id}/assign")
async def assign_conversation(
    conversation_id: UUID,
    body: AssignRequest | None = None,
    agent_id: Optional[UUID] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Assign a conversation to an agent.

    Accepts ``agent_id`` as a query param or ``user_id``/``agent_id`` in a
    JSON body (admin UI sends the latter).
    """
    from apps.api.modules.conversation.services import assign_conversation

    resolved = agent_id
    if resolved is None and body is not None:
        resolved = body.agent_id or body.user_id
    if resolved is None:
        raise HTTPException(status_code=422, detail="agent_id or user_id required")
    conv = await assign_conversation(user.tenant_id, conversation_id, resolved, session)
    return _serialize_conversation(conv)


@router.post("/{conversation_id}/close")
async def close_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Close a conversation."""
    from apps.api.modules.conversation.services import close_conversation
    conv = await close_conversation(user.tenant_id, conversation_id, session)
    return _serialize_conversation(conv)
