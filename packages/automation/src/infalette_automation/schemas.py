"""Automation package schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AutomationRuleCreate(BaseModel):
    """Schema for creating an automation rule."""

    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: dict = Field(default_factory=dict)
    conditions: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    priority: int = 0
    status: str = "draft"


class AutomationRuleRead(BaseModel):
    """Schema for reading an automation rule."""

    model_config = {"from_attributes": True}

    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    trigger_type: str
    trigger_config: dict
    conditions: list[dict]
    status: str
    priority: int
    created_at: datetime
    updated_at: datetime


class AutomationActionCreate(BaseModel):
    """Schema for creating an automation action."""

    action_type: str
    config: dict = Field(default_factory=dict)
    order: int = 0


class TriggerEvent(BaseModel):
    """Schema for a trigger event."""

    event_type: str
    tenant_id: UUID
    actor_id: Optional[UUID]
    payload: dict
    timestamp: datetime


class AutomationResult(BaseModel):
    """Schema for automation execution result."""

    rule_id: UUID
    matched: bool
    actions_executed: list[str]
    errors: list[str]
