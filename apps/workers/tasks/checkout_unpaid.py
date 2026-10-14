"""Unpaid-checkout reminder task (spec §3 automation trigger).

Finds checkouts still PENDING past a configured interval and records a
``checkout.unpaid`` domain event per checkout. Automation rules with the
``checkout_unpaid`` trigger type consume these events; the processor loop
and/or direct engine invocation executes reminder actions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import UUID

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def emit_unpaid_checkout_events(
    session: AsyncSession,
    tenant_id: UUID | None = None,
    interval_minutes: int = 60,
    limit_per_run: int = 500,
) -> dict:
    """Record ``checkout.unpaid`` events for stale pending checkouts.

    A checkout qualifies when it is PENDING and was created at least
    ``interval_minutes`` ago. Events are only emitted once per checkout
    per staleness window by checking for an existing event with the same
    checkout_id in the last 24h.
    """
    from infalette_database.models.checkout import Checkout, CheckoutStatus
    from infalette_database.models.event import Event
    from infalette_analytics.event_bus import record_event

    cutoff = datetime.utcnow() - timedelta(minutes=interval_minutes)
    dedupe_window = datetime.utcnow() - timedelta(hours=24)

    query = select(Checkout).where(
        Checkout.status == CheckoutStatus.PENDING,
        Checkout.created_at <= cutoff,
        # Never remind on ancient checkouts (>7 days) — treat as dead
        Checkout.created_at >= datetime.utcnow() - timedelta(days=7),
    )
    if tenant_id:
        query = query.where(Checkout.tenant_id == tenant_id)
    query = query.limit(limit_per_run)

    checkouts = list((await session.execute(query)).scalars().all())
    emitted = 0
    skipped_dupe = 0

    for checkout in checkouts:
        # Dedupe: skip if we already reminded this checkout in the window.
        # Load candidate events then filter in Python — payload queries must
        # work on both Postgres (JSONB) and SQLite (JSON) test dialects.
        candidates = (
            await session.execute(
                select(Event.payload_json).where(
                    Event.tenant_id == checkout.tenant_id,
                    Event.event_type == "checkout.unpaid",
                    Event.created_at >= dedupe_window,
                )
            )
        ).fetchall()
        already = any(
            str((row[0] or {}).get("checkout_id")) == str(checkout.id)
            for row in candidates
        )
        if already:
            skipped_dupe += 1
            continue

        await record_event(
            tenant_id=checkout.tenant_id,
            actor_id=checkout.customer_id,
            event_type="checkout.unpaid",
            payload={
                "checkout_id": str(checkout.id),
                "total_cents": checkout.total_cents,
                "customer_id": str(checkout.customer_id) if checkout.customer_id else None,
                "interval_minutes": interval_minutes,
            },
            session=session,
        )
        # Also persist checkout.abandoned so analytics segments and
        # automation rules can target this domain event explicitly.
        try:
            await record_event(
                tenant_id=checkout.tenant_id,
                actor_id=checkout.customer_id,
                event_type="checkout.abandoned",
                payload={
                    "checkout_id": str(checkout.id),
                    "total_cents": checkout.total_cents,
                    "customer_id": str(checkout.customer_id) if checkout.customer_id else None,
                    "interval_minutes": interval_minutes,
                },
                session=session,
            )
        except Exception:
            pass
        emitted += 1

    return {
        "checked": len(checkouts),
        "emitted": emitted,
        "skipped_duplicate": skipped_dupe,
    }


@shared_task(name="apps.workers.tasks.checkout_unpaid.checkout_unpaid_reminders")
def checkout_unpaid_reminders_task(tenant_id: str | None = None, interval_minutes: int = 60) -> dict:
    """Celery entry point for unpaid-checkout reminders."""

    async def _run() -> dict:
        from infalette_database.session import get_session_factory

        async with get_session_factory()() as session:
            return await emit_unpaid_checkout_events(
                session,
                tenant_id=UUID(tenant_id) if tenant_id else None,
                interval_minutes=interval_minutes,
            )

    try:
        result = asyncio.run(_run())
        logger.info("checkout_unpaid_reminders: %s", result)
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("checkout_unpaid_reminders failed: %s", exc, exc_info=True)
        return {"error": str(exc)}
