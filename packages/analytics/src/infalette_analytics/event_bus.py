"""Event bus for recording and publishing analytics events."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable
from uuid import UUID

from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.event import Event

logger = logging.getLogger(__name__)


class EventRecorder:
    """Records events to the database."""

    async def record_event(
        self,
        tenant_id: UUID,
        actor_id: Optional[UUID],
        event_type: str,
        payload: dict,
        session: AsyncSession,
        request_id: Optional[str] = None,
    ) -> Event:
        """Record an event to the database."""
        event = Event(
            tenant_id=tenant_id,
            actor_id=actor_id,
            event_type=event_type,
            payload_json=payload,
            request_id=request_id,
            created_at=datetime.utcnow(),
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        # Fire-and-forget PostHog capture after successful DB persist
        try:
            from infalette_analytics.posthog_client import PosthogClient

            PosthogClient().capture(event_type, str(tenant_id), payload)
        except Exception as exc:
            logger.debug(f"PostHog capture skipped for {event_type}: {exc}")

        return event


class EventBus:
    """Event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}
        self._recorder = EventRecorder()

    async def record_event(
        self,
        tenant_id: UUID,
        actor_id: Optional[UUID],
        event_type: str,
        payload: dict,
        session: AsyncSession,
        request_id: Optional[str] = None,
    ) -> Event:
        """Record an event to the database and publish to subscribers."""
        event = await self._recorder.record_event(
            tenant_id, actor_id, event_type, payload, session, request_id
        )

        # Publish to subscribers
        await self._publish(event_type, event)

        return event

    async def _publish(self, event_type: str, event: Event) -> None:
        """Publish an event to all subscribers."""
        subscribers = self._subscribers.get(event_type, [])
        for subscriber in subscribers:
            try:
                if hasattr(subscriber, '__call__'):
                    result = subscriber(event)
                    if hasattr(result, '__await__'):
                        await result
            except Exception as e:
                logger.error(f"Error in subscriber for {event_type}: {e}", exc_info=True)

    def subscribe(
        self,
        event_type: str,
        callback: Callable,
    ) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(
        self,
        event_type: str,
        callback: Callable,
    ) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    async def subscribe_to_events(
        self,
        tenant_id: UUID,
        event_types: list[str],
        session: AsyncSession,
        callback: Callable,
    ) -> None:
        """Subscribe to events for a tenant with filtering by type."""
        for event_type in event_types:
            self.subscribe(event_type, callback)

    async def get_events(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get events for a tenant."""
        query = select(Event).where(Event.tenant_id == tenant_id)
        if event_type:
            query = query.where(Event.event_type == event_type)
        query = query.order_by(Event.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_event_count(
        self,
        tenant_id: UUID,
        event_type: str,
        session: AsyncSession,
        days: int = 30,
    ) -> int:
        """Get the count of events for a tenant and event type."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(Event)
            .where(
                Event.tenant_id == tenant_id,
                Event.event_type == event_type,
                Event.created_at >= cutoff,
            )
        )
        return len(list(result.scalars().all()))


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def record_event(
    tenant_id: UUID,
    actor_id: Optional[UUID],
    event_type: str,
    payload: dict,
    session: AsyncSession,
    request_id: Optional[str] = None,
) -> Event:
    """Record an event using the global event bus."""
    bus = get_event_bus()
    return await bus.record_event(
        tenant_id, actor_id, event_type, payload, session, request_id
    )
