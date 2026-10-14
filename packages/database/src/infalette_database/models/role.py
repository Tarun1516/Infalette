"""Role model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, JSON, Enum as SAEnum

from infalette_database.base import Base


class UserRole(str, enum.Enum):
    """User role enum."""

    PLATFORM_OWNER = "platform_owner"
    TENANT_OWNER = "tenant_owner"
    STORE_MANAGER = "store_manager"
    MARKETING_AGENT = "marketing_agent"
    SUPPORT_AGENT = "support_agent"
    CUSTOMER = "customer"


class Role(Base):
    """Role model.

    Defines roles and their permissions for RBAC.
    """

    __tablename__ = "roles"

    name = Column(SAEnum(UserRole, native_enum=False, length=50), unique=True, nullable=False)
    permissions_json = Column(JSON, nullable=False, default=dict)
