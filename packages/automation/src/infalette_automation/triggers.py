"""Automation trigger evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_automation.schemas import TriggerEvent


class TriggerEngine:
    """Evaluates trigger conditions for automation rules."""

    TRIGGER_TYPES = {
        "order.created": "Order created",
        "order.status_changed": "Order status changed",
        "customer.created": "Customer created",
        "lead.created": "Lead created",
        "lead.status_changed": "Lead status changed",
        "checkout.created": "Checkout created",
        "payment.succeeded": "Payment succeeded",
        "cart.abandoned": "Cart abandoned",
        "conversation.created": "Conversation created",
        "conversation.message_received": "Message received",
        "product.low_stock": "Low stock alert",
        "subscription.renewed": "Subscription renewed",
        "subscription.expired": "Subscription expired",
    }

    # Mapping from AutomationTriggerType values (rule vocabulary) to the
    # domain-event types that can satisfy them (event-bus vocabulary).
    TRIGGER_TYPE_EVENT_MAP = {
        "comment_keyword": ["conversation.message_received", "comment.received"],
        "dm_product_sku": ["conversation.message_received", "message.received"],
        "story_response": ["conversation.message_received"],
        "whatsapp_flow": ["conversation.message_received"],
        "checkout_unpaid": ["checkout.unpaid", "cart.abandoned", "checkout.created", "checkout.abandoned"],
        "cart_abandoned": ["cart.abandoned"],
    }

    def evaluate_trigger(
        self,
        trigger_config: dict,
        event: TriggerEvent,
    ) -> bool:
        """Evaluate if an event matches a trigger configuration."""
        event_type = trigger_config.get("event_type")
        if event_type and event_type != event.event_type:
            return False

        # Check additional conditions in trigger config
        conditions = trigger_config.get("conditions", [])
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            event_value = event.payload.get(field)

            if not self._evaluate_condition(event_value, operator, value):
                return False

        # Keyword gate (spec §3): comment_keyword rules must match a
        # configured keyword ("buy", "price", "link", ...) against the
        # message/comment text, not just any inbound message.
        keywords = trigger_config.get("keywords") or []
        text_field = event.payload.get("text") or event.payload.get(
            "message_text"
        ) or event.payload.get("comment_text") or ""
        if keywords and not any(kw.lower() in str(text_field).lower() for kw in keywords):
            return False

        return True

    def _evaluate_condition(
        self,
        event_value,
        operator: str,
        expected_value,
    ) -> bool:
        """Evaluate a single condition."""
        if operator == "equals":
            return event_value == expected_value
        elif operator == "not_equals":
            return event_value != expected_value
        elif operator == "contains":
            return expected_value in str(event_value or "")
        elif operator == "not_contains":
            return expected_value not in str(event_value or "")
        elif operator == "greater_than":
            return (event_value or 0) > expected_value
        elif operator == "less_than":
            return (event_value or 0) < expected_value
        elif operator == "greater_than_or_equal":
            return (event_value or 0) >= expected_value
        elif operator == "less_than_or_equal":
            return (event_value or 0) <= expected_value
        elif operator == "in":
            return event_value in expected_value
        elif operator == "not_in":
            return event_value not in expected_value
        elif operator == "exists":
            return event_value is not None
        elif operator == "not_exists":
            return event_value is None
        return True

    async def get_matching_rules(
        self,
        event: TriggerEvent,
        session: AsyncSession,
    ) -> list:
        """Get all automation rules that match an event."""
        from infalette_database.models.automation_rule import AutomationRule

        result = await session.execute(
            select(AutomationRule).where(
                AutomationRule.tenant_id == event.tenant_id,
                AutomationRule.status == "active",
            )
        )
        rules = list(result.scalars().all())

        matching = []
        for rule in rules:
            trigger_config = dict(getattr(rule, "trigger_config", None) or {})
            # Merge keyword/condition config stored under conditions_json so
            # keyword gating applies regardless of which field operators used.
            cond_json = getattr(rule, "conditions_json", None) or {}
            if isinstance(cond_json, dict):
                if cond_json.get("conditions") and not trigger_config.get("conditions"):
                    trigger_config["conditions"] = cond_json["conditions"]
                if cond_json.get("keywords") and not trigger_config.get("keywords"):
                    trigger_config["keywords"] = cond_json.get("keywords")

            if not trigger_config.get("event_type"):
                # Derive the event type from the rule's trigger_type enum
                # (rule vocabulary -> event vocabulary).
                trigger_type = getattr(rule, "trigger_type", None)
                trigger_value = (
                    getattr(trigger_type, "value", trigger_type)
                    if trigger_type is not None
                    else None
                )
                mapped = self.TRIGGER_TYPE_EVENT_MAP.get(trigger_value)
                if mapped is None:
                    # Rule may already use an event-style type directly.
                    mapped = [trigger_value] if trigger_value else []
                if event.event_type not in mapped:
                    continue
                # Even with derived event types, evaluate any configured
                # conditions/keywords — a comment_keyword rule must not fire
                # on every inbound message.
                if not self.evaluate_trigger(trigger_config, event):
                    continue
            elif not self.evaluate_trigger(trigger_config, event):
                continue
            matching.append(rule)

        return matching

    def get_available_triggers(self) -> list[dict]:
        """Get list of available trigger types."""
        return [
            {"type": t, "name": n}
            for t, n in self.TRIGGER_TYPES.items()
        ]
