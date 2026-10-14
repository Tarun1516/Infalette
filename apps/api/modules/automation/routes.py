"""Automation management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import Feature, require_feature, enforce_quota

router = APIRouter()


@router.get("/")
async def list_automation_rules(
    status: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
    plan=Depends(require_feature(Feature.INSTAGRAM_AUTOMATION)),
):
    """List automation rules for the tenant."""
    from apps.api.modules.automation.services import list_automation_rules
    return await list_automation_rules(user.tenant_id, session, status)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_automation_rule(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
    plan=Depends(require_feature(Feature.INSTAGRAM_AUTOMATION)),
    quota=Depends(enforce_quota("automations")),
):
    """Create a new automation rule (plan quota enforced)."""
    from apps.api.modules.automation.services import create_automation_rule
    return await create_automation_rule(user.tenant_id, data, session)


@router.get("/{rule_id}")
async def get_automation_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get an automation rule by ID."""
    from apps.api.modules.automation.services import get_automation_rule
    rule = await get_automation_rule(user.tenant_id, rule_id, session)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    return rule


@router.patch("/{rule_id}")
async def update_automation_rule(
    rule_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update an automation rule."""
    from apps.api.modules.automation.services import update_automation_rule
    return await update_automation_rule(user.tenant_id, rule_id, data, session)


@router.delete("/{rule_id}")
async def delete_automation_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete an automation rule."""
    from apps.api.modules.automation.services import delete_automation_rule
    await delete_automation_rule(user.tenant_id, rule_id, session)
    return {"message": "Automation rule deleted"}


@router.post("/{rule_id}/toggle")
async def toggle_automation_rule(
    rule_id: UUID,
    enabled: bool,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Enable or disable an automation rule."""
    from apps.api.modules.automation.services import toggle_automation_rule
    return await toggle_automation_rule(user.tenant_id, rule_id, enabled, session)


@router.post("/{rule_id}/test")
async def test_automation_rule(
    rule_id: UUID,
    test_data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Test an automation rule with sample data."""
    from apps.api.modules.automation.services import test_automation_rule
    return await test_automation_rule(user.tenant_id, rule_id, test_data, session)


@router.get("/{rule_id}/actions")
async def list_rule_actions(
    rule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get all actions for an automation rule."""
    from apps.api.modules.automation.services import list_rule_actions
    return await list_rule_actions(rule_id, session)
