"""Automation management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.automation_rule import AutomationRule
from infalette_database.models.automation_action import AutomationAction
from infalette_analytics.event_bus import record_event


async def list_automation_rules(
    tenant_id: UUID,
    session: AsyncSession,
    status: Optional[str] = None,
) -> list[AutomationRule]:
    """List automation rules for a tenant."""
    query = select(AutomationRule).where(AutomationRule.tenant_id == tenant_id)
    if status:
        query = query.where(AutomationRule.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_automation_rule(
    tenant_id: UUID,
    rule_id: UUID,
    session: AsyncSession,
) -> AutomationRule | None:
    """Get an automation rule by ID."""
    result = await session.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_automation_rule(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> AutomationRule:
    """Create a new automation rule."""
    rule = AutomationRule(
        tenant_id=tenant_id,
        name=data.get("name"),
        description=data.get("description", ""),
        trigger_type=data.get("trigger_type"),
        trigger_config=data.get("trigger_config", {}),
        status=data.get("status", "draft"),
        priority=data.get("priority", 0),
        conditions_json={"conditions": data.get("conditions", [])},
    )
    session.add(rule)
    await session.flush()

    # Create actions
    actions = data.get("actions", [])
    for action_data in actions:
        action = AutomationAction(
            rule_id=rule.id,
            action_type=action_data.get("action_type"),
            config=action_data.get("config", {}),
            order=action_data.get("order", 0),
        )
        session.add(action)

    await session.commit()
    await session.refresh(rule)

    await record_event(
        tenant_id=tenant_id,
        actor_id=None,
        event_type="automation.rule_created",
        payload={"rule_id": str(rule.id), "name": rule.name},
        session=session,
    )

    return rule


async def update_automation_rule(
    tenant_id: UUID,
    rule_id: UUID,
    data: dict,
    session: AsyncSession,
) -> AutomationRule | None:
    """Update an automation rule."""
    rule = await get_automation_rule(tenant_id, rule_id, session)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")

    for key, value in data.items():
        if hasattr(rule, key) and value is not None:
            setattr(rule, key, value)

    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_automation_rule(
    tenant_id: UUID,
    rule_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete an automation rule."""
    await session.execute(
        delete(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def toggle_automation_rule(
    tenant_id: UUID,
    rule_id: UUID,
    enabled: bool,
    session: AsyncSession,
) -> AutomationRule | None:
    """Enable or disable an automation rule."""
    rule = await get_automation_rule(tenant_id, rule_id, session)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")

    await session.execute(
        update(AutomationRule)
        .where(AutomationRule.id == rule_id)
        .values(status="active" if enabled else "draft")
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_automation_rule(tenant_id, rule_id, session)


async def test_automation_rule(
    tenant_id: UUID,
    rule_id: UUID,
    test_data: dict,
    session: AsyncSession,
) -> dict:
    """Test an automation rule with sample data."""
    rule = await get_automation_rule(tenant_id, rule_id, session)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")

    # Simulate rule evaluation
    cfg = rule.trigger_config or {}
    conditions = (
        rule.conditions_json.get("conditions")
        if isinstance(rule.conditions_json, dict) and "conditions" in (rule.conditions_json or {})
        else (rule.conditions_json if isinstance(rule.conditions_json, list) else [])
    ) or cfg.get("conditions") or []
    matched = True
    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        test_value = test_data.get(field)

        if operator == "equals" and test_value != value:
            matched = False
        elif operator == "contains" and value not in str(test_value or ""):
            matched = False
        elif operator == "greater_than" and not (test_value or 0) > value:
            matched = False

    return {
        "rule_id": str(rule_id),
        "matched": matched,
        "actions": [a.action_type for a in rule.actions] if hasattr(rule, 'actions') else [],
    }


async def list_rule_actions(
    rule_id: UUID,
    session: AsyncSession,
) -> list[AutomationAction]:
    """Get all actions for an automation rule."""
    result = await session.execute(
        select(AutomationAction).where(AutomationAction.rule_id == rule_id)
    )
    return list(result.scalars().all())
