"""Automation rule processing task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_automation.engine import AutomationEngine
from infalette_automation.processor import AutomationProcessor
from infalette_automation.schemas import TriggerEvent

logger = logging.getLogger(__name__)


async def process_automation_rules(
    session: AsyncSession,
    tenant_id: UUID = None,
    event_type: str = None,
    payload: dict = None,
    actor_id: UUID = None,
) -> dict:
    """Process automation rules for an event."""
    engine = AutomationEngine()

    event = TriggerEvent(
        event_type=event_type or "manual",
        tenant_id=tenant_id,
        actor_id=actor_id,
        payload=payload or {},
        timestamp=datetime.utcnow(),
    )

    results = await engine.process_event(event, session)

    return {
        "rules_processed": len(results),
        "results": [r.model_dump() for r in results],
    }


@shared_task(name="apps.workers.tasks.automation.process_automation_rules")
def process_automation_rules_task(
    tenant_id: str, event_type: str, payload: dict, actor_id: str = None
) -> dict:
    """Celery entry point: run one TriggerEvent through the engine."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            return await process_automation_rules(
                session,
                tenant_id=UUID(tenant_id),
                event_type=event_type,
                payload=payload or {},
                actor_id=UUID(actor_id) if actor_id else None,
            )

    return asyncio.run(_run())


async def run_processor_once(
    poll_interval: float = 1.0,
    max_iterations: int = 1,
) -> dict:
    """Single bounded iteration of the AutomationProcessor loop.

    Used by the beat-scheduled task so each tick advances the high-water
    mark without blocking the worker. The processor keeps an internal
    high-water mark on Event.created_at, so subsequent ticks process
    only newly created events.
    """
    from infalette_database.session import get_session_factory

    processor = AutomationProcessor()
    factory = get_session_factory()

    # Disable the processor's own sleep so the beat tick can do a single
    # pass and return immediately.
    processor._running = True

    processed = 0
    try:
        from infalette_database.models.event import Event

        async with factory() as session:
            from infalette_automation.schemas import TriggerEvent as _TriggerEvent

            # Process any events whose automation rules are time-based
            # (e.g. delay/wait conditions). For a beat tick, scan a small
            # window of recent events and let the engine re-evaluate.
            result = await session.execute(
                select(Event).order_by(Event.created_at.desc()).limit(50)
            )
            events = list(result.scalars().all())
            for event in events:
                trigger = TriggerEvent(
                    event_type=event.event_type,
                    tenant_id=event.tenant_id,
                    actor_id=event.actor_id,
                    payload=dict(event.payload_json or {}),
                    timestamp=event.created_at or datetime.utcnow(),
                )
                await processor.process_event(trigger, session)
                processed += 1
                if processed >= max_iterations * 50:
                    break
    finally:
        processor.stop()

    return {"processed": processed}


@shared_task(name="apps.workers.tasks.automation.run_automation_processor")
def run_automation_processor_task() -> dict:
    """Beat entry point: run the AutomationProcessor one tick.

    Drains a small window of recent events through the engine so rules
    that depend on non-webhook triggers (time-based, scheduled, etc.)
    still fire even when no inbound webhook is present.
    """
    try:
        result = asyncio.run(run_processor_once())
        logger.info("automation_processor_tick: %s", result)
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("automation_processor_tick failed: %s", exc, exc_info=True)
        return {"error": str(exc)}
