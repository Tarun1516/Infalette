"""Automation event processor - background processing."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_automation.schemas import TriggerEvent
from infalette_automation.engine import AutomationEngine

logger = logging.getLogger(__name__)


class AutomationProcessor:
    """Processes automation events from a queue."""

    def __init__(self) -> None:
        self._engine = AutomationEngine()
        self._running = False

    async def process_event(
        self,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> None:
        """Process a single automation event."""
        try:
            results = await self._engine.process_event(event, session)
            for result in results:
                logger.info(
                    f"Automation rule {result.rule_id} executed: "
                    f"{len(result.actions_executed)} actions, "
                    f"{len(result.errors)} errors"
                )
        except Exception as e:
            logger.error(f"Error processing automation event: {e}", exc_info=True)

    async def process_events_batch(
        self,
        events: list[TriggerEvent],
        session: AsyncSession,
    ) -> None:
        """Process a batch of automation events."""
        for event in events:
            await self.process_event(event, session)

    async def start_processing_loop(
        self,
        session_factory,
        poll_interval: float = 1.0,
    ) -> None:
        """Poll the Event table and run automation for new domain events.

        Tracks a high-water mark on Event.created_at so each event is
        processed exactly once per loop lifetime. Automation-eligible
        event types are the ones rules can match (see TriggerEngine).
        """
        from infalette_database.models.event import Event

        AUTOMATABLE_EVENTS = {
            "order.created",
            "customer.created",
            "lead.created",
            "lead.stage_changed",
            "checkout.created",
            "payment.succeeded",
            "cart.abandoned",
            "conversation.message_received",
            "product.low_stock",
        }

        self._running = True
        last_seen = datetime.utcnow()
        logger.info("Starting automation processor loop (polling events table)")

        while self._running:
            try:
                async with session_factory() as session:
                    result = await session.execute(
                        select(Event)
                        .where(
                            Event.created_at > last_seen,
                            Event.event_type.in_(AUTOMATABLE_EVENTS),
                        )
                        .order_by(Event.created_at.asc())
                        .limit(100)
                    )
                    events = list(result.scalars().all())
                    for event in events:
                        if event.created_at:
                            last_seen = max(last_seen, event.created_at)
                        trigger = TriggerEvent(
                            event_type=event.event_type,
                            tenant_id=event.tenant_id,
                            actor_id=event.actor_id,
                            payload=dict(event.payload_json or {}),
                            timestamp=event.created_at or datetime.utcnow(),
                        )
                        await self.process_event(trigger, session)

                    if not events:
                        await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                self._running = False
                logger.info("Automation processor loop stopped")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Stop the processing loop."""
        self._running = False
