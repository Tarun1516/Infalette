"""Tenant model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class TenantStatus(str, enum.Enum):
    """Tenant status enum.

    Note: values are uppercase to match the postgres ``tenantstatus`` enum
    type that alembic 001 created. The Python ``str`` mixin makes these
    values serialise as plain strings in JSON/SQL.
    """

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class Tenant(Base):
    """Tenant model — the isolation root; does not carry tenant_id itself.

    Each influencer gets a tenant with their own domain, products,
    payment account, social accounts, theme configuration and analytics.
    """

    __tablename__ = "tenants"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    # Plan is stored as a string (matches alembic 001: tenants.plan) so
    # feature-flag plan resolution works without a join; plan_id retained
    # for subscription linkage.
    plan = Column(String(50), default="store", nullable=False)
    plan_id = Column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True
    )
    status = Column(
        # native_enum=False tells SQLAlchemy to treat the column as a plain
        # VARCHAR(20) on the Postgres side (matches the column alembic 001
        # actually created) while still letting us pass TenantStatus enum
        # values from Python. Without this the SAEnum emits a cast to the
        # postgres `tenantstatus` enum type, which doesn't exist because
        # the column itself was never created as one.
        SAEnum(TenantStatus, name="tenantstatus", native_enum=False, length=20),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )

    # Relationships
    # plan = relationship("Plan")
    # domains = relationship("Domain", back_populates="tenant")
    # users = relationship("User", back_populates="tenant")
    # stores = relationship("Store", back_populates="tenant")
