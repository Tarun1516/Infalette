"""SQLAlchemy base and mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all models."""

    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at = Column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class TenantMixin:
    """Mixin for tenant-scoped models.

    All tenant-owned records must include a tenant_id column.
    Tenant context is resolved from the domain or authenticated account
    and enforced in the data-access layer.
    """

    __allow_unmapped__ = True

    @declared_attr
    def tenant_id(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=False,
            index=True,
        )
