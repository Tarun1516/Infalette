"""Automation engine - main orchestrator."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_automation.schemas import TriggerEvent, AutomationResult
from infalette_automation.triggers import TriggerEngine
from infalette_automation.actions import ActionExecutor


class AutomationEngine:
    """Main automation engine that processes events and executes actions."""

    def __init__(self) -> None:
        self._trigger_engine = TriggerEngine()
        self._action_executor = ActionExecutor()

    async def process_event(
        self,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> list[AutomationResult]:
        """Process an event through the automation engine."""
        # Get matching rules
        matching_rules = await self._trigger_engine.get_matching_rules(event, session)

        results = []
        for rule in matching_rules:
            result = await self._execute_rule(rule, event, session)
            results.append(result)

        return results

    async def _execute_rule(
        self,
        rule,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> AutomationResult:
        """Execute a single automation rule.

        Guards:
        - execution_limit: total executions of this rule are counted from
          durable ``automation.triggered`` events; the rule stops firing
          once the configured cap is reached.
        - cooldown: a rule fires at most once per minute per tenant by
          default, preventing webhook-storm duplicates.
        """
        from datetime import timedelta

        from infalette_database.models.automation_action import AutomationAction
        from infalette_database.models.event import Event
        from infalette_analytics.event_bus import record_event

        # --- execution accounting (durable) -----------------------------
        execution_count = 0
        last_triggered_at = None
        try:
            since = getattr(rule, "created_at", None) or (
                datetime.utcnow() - timedelta(days=90)
            )
            rows = await session.execute(
                select(Event)
                .where(
                    Event.tenant_id == event.tenant_id,
                    Event.event_type == "automation.triggered",
                    Event.created_at >= since,
                )
                .order_by(Event.created_at.desc())
                .limit(500)
            )
            for ev in rows.scalars():
                payload = getattr(ev, "payload_json", None) or {}
                if str(payload.get("rule_id")) == str(rule.id):
                    execution_count += 1
                    if last_triggered_at is None or ev.created_at > last_triggered_at:
                        last_triggered_at = ev.created_at
        except Exception:
            execution_count = 0  # fail open on accounting errors only

        limit = getattr(rule, "execution_limit", None)
        if limit is not None and limit > 0 and execution_count >= limit:
            return AutomationResult(
                rule_id=rule.id,
                matched=False,
                actions_executed=[],
                errors=[f"execution_limit reached ({limit})"],
            )

        cooldown = timedelta(seconds=60)
        if last_triggered_at is not None and datetime.utcnow() - (
            last_triggered_at if last_triggered_at.tzinfo is None else last_triggered_at.replace(tzinfo=None)
        ) < cooldown:
            return AutomationResult(
                rule_id=rule.id,
                matched=False,
                actions_executed=[],
                errors=["cooldown active"],
            )

        # Get actions for this rule
        result = await session.execute(
            select(AutomationAction)
            .where(AutomationAction.rule_id == rule.id)
            .order_by(AutomationAction.order)
        )
        actions = list(result.scalars().all())

        actions_executed = []
        errors = []

        # Record the trigger durably BEFORE executing so limits hold even
        # under concurrent processing and across restarts.
        try:
            await record_event(
                tenant_id=event.tenant_id,
                actor_id=event.actor_id,
                event_type="automation.triggered",
                payload={
                    "rule_id": str(rule.id),
                    "source_event": event.event_type,
                },
                session=session,
            )
        except Exception:
            pass

        for action in actions:
            try:
                action_result = await self._action_executor.execute_action(
                    action.action_type,
                    action.config,
                    event,
                    session,
                )
                actions_executed.append(action.action_type)
                if action_result.get("status") == "error":
                    errors.append(action_result.get("error", "Unknown error"))
            except Exception as e:
                errors.append(str(e))

        return AutomationResult(
            rule_id=rule.id,
            matched=True,
            actions_executed=actions_executed,
            errors=errors,
        )

    async def process_event_from_payload(
        self,
        tenant_id: UUID,
        event_type: str,
        payload: dict,
        actor_id: Optional[UUID] = None,
        session: AsyncSession = None,
    ) -> list[AutomationResult]:
        """Process an event from a raw payload."""
        event = TriggerEvent(
            event_type=event_type,
            tenant_id=tenant_id,
            actor_id=actor_id,
            payload=payload,
            timestamp=datetime.utcnow(),
        )
        return await self.process_event(event, session)

    def get_available_triggers(self) -> list[dict]:
        """Get available trigger types."""
        return self._trigger_engine.get_available_triggers()

    def get_available_actions(self) -> list[dict]:
        """Get available action types."""
        return self._action_executor.get_available_actions()
