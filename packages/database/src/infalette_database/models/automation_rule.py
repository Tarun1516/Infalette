"""AutomationRule model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, JSON, Integer, Text, Enum as SAEnum
from sqlalchemy.orm import synonym

from infalette_database.base import Base, TenantMixin


class AutomationRuleStatus(str, enum.Enum):
    """Automation rule status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class AutomationTriggerType(str, enum.Enum):
    """Automation trigger type enum."""

    COMMENT_KEYWORD = "comment_keyword"
    DM_PRODUCT_SKU = "dm_product_sku"
    STORY_RESPONSE = "story_response"
    WHATSAPP_FLOW = "whatsapp_flow"
    CHECKOUT_UNPAID = "checkout_unpaid"


class AutomationActionType(str, enum.Enum):
    """Automation action type enum."""

    PRIVATE_REPLY = "private_reply"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    CHECKOUT_LINK = "checkout_link"
    LEAD_CREATE = "lead_create"
    ASSIGN_AGENT = "assign_agent"
    REMINDER_SCHEDULE = "reminder_schedule"
    TAG = "tag"


class AutomationRule(Base, TenantMixin):
    """Automation rule model.

    Rules with triggers, conditions, actions, status and execution limits.
    """

    __tablename__ = "automation_rules"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(
        SAEnum(AutomationTriggerType, native_enum=False, length=50), nullable=False, index=True
    )
    # Event-engine trigger configuration (event_type + conditions). Matches
    # the alembic 001 `trigger_config` JSONB column read by TriggerEngine.
    trigger_config = Column(JSON, nullable=False, default=dict)
    conditions_json = Column(JSON, nullable=False, default=dict)
    actions_json = Column(JSON, nullable=False, default=list)
    # Legacy 001 column name; kept as an alias of conditions_json so both
    # naming conventions work (services pass `conditions=[...]`).
    conditions = synonym("conditions_json")
    status = Column(
        SAEnum(AutomationRuleStatus, native_enum=False, length=50), default=AutomationRuleStatus.DRAFT, nullable=False
    )
    priority = Column(Integer, default=0, nullable=False)
    execution_limit = Column(Integer, nullable=True)
