"""Plan model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, Integer, JSON, Enum as SAEnum

from infalette_database.base import Base


class PlanType(str, enum.Enum):
    """Plan type enum."""

    STORE = "store"
    STORE_AUTOMATION = "store_automation"
    STORE_AUTOMATION_CRM = "store_automation_crm"


class Plan(Base):
    """Plan model.

    Defines subscription plans with feature flags and quotas.
    Capabilities are implemented through feature flags and quotas,
    not separate applications.
    """

    __tablename__ = "plans"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    plan_type = Column(SAEnum(PlanType, native_enum=False, length=50), nullable=False)
    price_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    interval = Column(String(20), default="month", nullable=False)
    features_json = Column(JSON, nullable=False)
