"""Integration tests for the automation engine."""

import pytest
from uuid import uuid4
from datetime import datetime

from infalette_automation.engine import AutomationEngine
from infalette_automation.schemas import TriggerEvent
from infalette_automation.triggers import TriggerEngine
from infalette_automation.actions import ActionExecutor


@pytest.mark.asyncio
async def test_trigger_engine_evaluate_trigger():
    """Test trigger evaluation."""
    engine = TriggerEngine()
    event = TriggerEvent(
        event_type="order.created",
        tenant_id=uuid4(),
        actor_id=uuid4(),
        payload={"order_id": "123", "status": "confirmed"},
        timestamp=datetime.utcnow(),
    )

    trigger_config = {"event_type": "order.created"}
    assert engine.evaluate_trigger(trigger_config, event) is True

    trigger_config = {"event_type": "order.status_changed"}
    assert engine.evaluate_trigger(trigger_config, event) is False


@pytest.mark.asyncio
async def test_trigger_engine_with_conditions():
    """Test trigger evaluation with conditions."""
    engine = TriggerEngine()
    event = TriggerEvent(
        event_type="order.created",
        tenant_id=uuid4(),
        actor_id=uuid4(),
        payload={"order_id": "123", "status": "confirmed", "total_cents": 50000},
        timestamp=datetime.utcnow(),
    )

    trigger_config = {
        "event_type": "order.created",
        "conditions": [
            {"field": "status", "operator": "equals", "value": "confirmed"},
            {"field": "total_cents", "operator": "greater_than", "value": 10000},
        ],
    }
    assert engine.evaluate_trigger(trigger_config, event) is True

    trigger_config = {
        "event_type": "order.created",
        "conditions": [
            {"field": "status", "operator": "equals", "value": "pending"},
        ],
    }
    assert engine.evaluate_trigger(trigger_config, event) is False


@pytest.mark.asyncio
async def test_action_executor_get_available_actions():
    """Test getting available actions."""
    executor = ActionExecutor()
    actions = executor.get_available_actions()
    assert len(actions) > 0
    assert any(a["type"] == "send_email" for a in actions)
    assert any(a["type"] == "create_checkout_link" for a in actions)


@pytest.mark.asyncio
async def test_automation_engine_get_available_triggers():
    """Test getting available triggers."""
    engine = AutomationEngine()
    triggers = engine.get_available_triggers()
    assert len(triggers) > 0
    assert any(t["type"] == "order.created" for t in triggers)


@pytest.mark.asyncio
async def test_automation_engine_process_event_no_rules(db_session, tenant_id):
    """Test processing an event with no matching rules."""
    engine = AutomationEngine()
    event = TriggerEvent(
        event_type="order.created",
        tenant_id=tenant_id,
        actor_id=uuid4(),
        payload={"order_id": "123"},
        timestamp=datetime.utcnow(),
    )

    results = await engine.process_event(event, db_session)
    assert results == []
