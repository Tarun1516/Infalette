"""Instagram webhook handler."""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.conversation import Conversation, ConversationChannel
from infalette_database.models.message import Message, MessageDirection
from infalette_database.models.lead import Lead
from infalette_database.models.social_identity import SocialIdentity
from infalette_automation.engine import AutomationEngine
from infalette_automation.schemas import TriggerEvent
from infalette_config import get_settings
from infalette_integrations.base import allow_unverified_webhooks

logger = logging.getLogger(__name__)


class InstagramWebhookHandler:
    """Handles Instagram webhook events."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._webhook_secret = self._settings.social.instagram_webhook_secret

    async def verify_webhook(
        self,
        mode: str,
        verify_token: str,
        challenge: str,
    ) -> Optional[str]:
        """Verify the webhook subscription.

        Uses INSTAGRAM_VERIFY_TOKEN when set; falls back to the app id
        (client id) for backwards compatibility.
        """
        expected = (
            self._settings.social.instagram_verify_token
            or self._settings.social.instagram_client_id
        )
        if mode == "subscribe" and expected and verify_token == expected:
            return challenge
        return None

    async def verify_webhook_hmac(
        self,
        payload: dict,
        signature: str,
        raw_body: str | bytes | None = None,
    ) -> bool:
        """Verify the webhook HMAC signature.

        Meta signs the exact raw request bytes — verification must hash
        those bytes, not a re-serialization of the parsed payload. When
        ``raw_body`` is unavailable (legacy callers), fall back to the
        canonical JSON dump.
        """
        if not self._webhook_secret:
            if not allow_unverified_webhooks():
                return False
            return True

        if raw_body is not None:
            body = raw_body.encode() if isinstance(raw_body, str) else raw_body
        else:
            body = json.dumps(payload, sort_keys=True).encode()

        expected = hmac.new(
            self._webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_comment_webhook(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Process a comment webhook from Instagram."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        comment_data = changes.get("value", {}).get("comment", {})

        comment_id = comment_data.get("id", "")
        comment_text = comment_data.get("text", "")
        media_id = comment_data.get("media_id", "")
        username = comment_data.get("from", {}).get("username", "")
        ig_user_id = entry.get("id", "")

        # Find or create social identity
        result = await session.execute(
            select(SocialIdentity).where(
                SocialIdentity.provider == "instagram",
                SocialIdentity.provider_user_id == ig_user_id,
            )
        )
        identity = result.scalar_one_or_none()

        if not identity:
            return {"status": "error", "error": "Social identity not found"}

        # Find or create conversation
        result = await session.execute(
            select(Conversation).where(
                Conversation.tenant_id == identity.tenant_id,
                Conversation.channel == ConversationChannel.INSTAGRAM,
                Conversation.external_id == media_id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                tenant_id=identity.tenant_id,
                channel=ConversationChannel.INSTAGRAM,
                external_id=media_id,
                customer_name=username,
                status="active",
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

        # Create message (dedupe on provider comment id — Meta retries)
        existing = None
        if comment_id:
            result = await session.execute(
                select(Message).where(Message.external_id == comment_id)
            )
            existing = result.scalar_one_or_none()
        if existing is not None:
            return {
                "status": "duplicate_ignored",
                "conversation_id": str(conversation.id),
                "message_id": str(existing.id),
            }

        message = Message(
            conversation_id=conversation.id,
            direction=MessageDirection.INBOUND,
            content=comment_text,
            external_id=comment_id,
            status="received",
        )
        session.add(message)
        await session.commit()

        # Find or create lead
        result = await session.execute(
            select(Lead).where(
                Lead.tenant_id == identity.tenant_id,
                Lead.email == f"{username}@instagram.com",
            )
        )
        lead = result.scalar_one_or_none()

        if not lead:
            lead = Lead(
                tenant_id=identity.tenant_id,
                first_name=username,
                email=f"{username}@instagram.com",
                source="instagram",
                status="new",
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)

        # Persist the funnel stage-1 domain event (comments count too)
        try:
            from infalette_analytics.event_bus import record_event

            await record_event(
                tenant_id=identity.tenant_id,
                actor_id=lead.id,
                event_type="conversation.message_received",
                payload={
                    "conversation_id": str(conversation.id),
                    "lead_id": str(lead.id),
                    "comment_id": comment_id,
                    "text": comment_text,
                    "message_text": comment_text,
                    "comment_text": comment_text,
                    "media_id": media_id,
                    "username": username,
                    "channel": "instagram_comment",
                    "commenter_id": None,
                },
                session=session,
            )
            # Spec §4 canonical event name for comment ingestion.
            await record_event(
                tenant_id=identity.tenant_id,
                actor_id=lead.id,
                event_type="comment.received",
                payload={
                    "conversation_id": str(conversation.id),
                    "lead_id": str(lead.id),
                    "comment_id": comment_id,
                    "media_id": media_id,
                    "username": username,
                    "text": comment_text,
                },
                session=session,
            )
        except Exception:
            pass

        # Trigger automation
        engine = AutomationEngine()
        event = TriggerEvent(
            event_type="conversation.message_received",
            tenant_id=identity.tenant_id,
            actor_id=lead.id,
            payload={
                "lead_id": str(lead.id),
                "conversation_id": str(conversation.id),
                "commenter_id": comment_data.get("from", {}).get("id", ""),
                "comment_id": comment_id,
                "comment_text": comment_text,
                "text": comment_text,
                "media_id": media_id,
                "username": username,
                "channel": "instagram_comment",
            },
            timestamp=message.created_at or __import__("datetime").datetime.utcnow(),
        )
        await engine.process_event(event, session)

        return {
            "status": "processed",
            "conversation_id": str(conversation.id),
            "lead_id": str(lead.id),
            "message_id": str(message.id),
        }

    async def process_dm_webhook(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> dict:
        """Process a DM webhook from Instagram."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        message_data = changes.get("value", {})

        message_id = message_data.get("id", "")
        message_text = message_data.get("text", "")
        from_username = message_data.get("from", {}).get("username", "")
        ig_user_id = entry.get("id", "")

        # Find social identity
        result = await session.execute(
            select(SocialIdentity).where(
                SocialIdentity.provider == "instagram",
                SocialIdentity.provider_user_id == ig_user_id,
            )
        )
        identity = result.scalar_one_or_none()

        if not identity:
            return {"status": "error", "error": "Social identity not found"}

        # Find or create conversation
        result = await session.execute(
            select(Conversation).where(
                Conversation.tenant_id == identity.tenant_id,
                Conversation.channel == ConversationChannel.INSTAGRAM,
                Conversation.external_id == f"dm_{from_username}",
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                tenant_id=identity.tenant_id,
                channel=ConversationChannel.INSTAGRAM,
                external_id=f"dm_{from_username}",
                customer_name=from_username,
                status="active",
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

        # Create message (dedupe on provider id — Meta retries deliveries)
        existing = None
        if message_id:
            result = await session.execute(
                select(Message).where(Message.external_id == message_id)
            )
            existing = result.scalar_one_or_none()
        if existing is not None:
            return {
                "status": "duplicate_ignored",
                "conversation_id": str(conversation.id),
                "message_id": str(existing.id),
            }

        message = Message(
            conversation_id=conversation.id,
            direction=MessageDirection.INBOUND,
            content=message_text,
            external_id=message_id,
            status="received",
        )
        session.add(message)
        await session.commit()

        # Find or create lead (DMs are a lead source per spec §3 CRM)
        result = await session.execute(
            select(Lead).where(
                Lead.tenant_id == identity.tenant_id,
                Lead.email == f"{from_username}@instagram.com",
            )
        )
        lead = result.scalar_one_or_none()
        if not lead:
            lead = Lead(
                tenant_id=identity.tenant_id,
                first_name=from_username,
                email=f"{from_username}@instagram.com",
                source="instagram",
                status="new",
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)

        conversation.lead_id = lead.id
        await session.commit()

        # Persist the funnel stage-1 domain event (analytics + processor loop)
        try:
            from infalette_analytics.event_bus import record_event

            await record_event(
                tenant_id=identity.tenant_id,
                actor_id=lead.id,
                event_type="conversation.message_received",
                payload={
                    "conversation_id": str(conversation.id),
                    "lead_id": str(lead.id),
                    "text": message_text,
                    "message_text": message_text,
                    "message_id": message_id,
                    "username": from_username,
                    "channel": "instagram_dm",
                    "commenter_id": None,
                },
                session=session,
            )
        except Exception:
            pass

        # Trigger automation (DM product-SKU rules match on this event)
        engine = AutomationEngine()
        event = TriggerEvent(
            event_type="conversation.message_received",
            tenant_id=identity.tenant_id,
            actor_id=lead.id,
            payload={
                "lead_id": str(lead.id),
                "conversation_id": str(conversation.id),
                "message_id": message_id,
                "message_text": message_text,
                "text": message_text,
                "username": from_username,
                "channel": "instagram_dm",
            },
            timestamp=message.created_at or __import__("datetime").datetime.utcnow(),
        )
        await engine.process_event(event, session)

        return {
            "status": "processed",
            "conversation_id": str(conversation.id),
            "lead_id": str(lead.id),
            "message_id": str(message.id),
        }

    async def deduplicate_events(
        self,
        payload: dict,
        session: AsyncSession,
    ) -> bool:
        """Check if an event has already been processed."""
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        message_data = changes.get("value", {})
        external_id = message_data.get("id", "")

        if not external_id:
            return False

        result = await session.execute(
            select(Message).where(Message.external_id == external_id)
        )
        return result.scalar_one_or_none() is not None

    async def handle_webhook_errors(
        self,
        error: Exception,
        payload: dict,
    ) -> None:
        """Handle webhook processing errors."""
        logger.error(f"Instagram webhook error: {error}", exc_info=True)
        logger.error(f"Payload: {json.dumps(payload, default=str)}")
