"""Customer model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, Text, JSON, Enum as SAEnum

from infalette_database.base import Base, TenantMixin


class CustomerStatus(str, enum.Enum):
    """Customer status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class Customer(Base, TenantMixin):
    """Customer model.

    Represents a person across website, Instagram and WhatsApp
    where identity can be lawfully matched.

    Alembic defines: email, first_name, last_name, phone, tags, status(String)
    This model keeps SAEnum status for type-safety while allowing string
    writes from services (e.g. status="active").
    """

    __tablename__ = "customers"

    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    # Alembic tags JSONB
    tags = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)
    # Legacy / extended fields – kept nullable for backward compat
    addresses_json = Column(JSON, nullable=False, default=list)
    consent_json = Column(JSON, nullable=False, default=dict)
    status = Column(
        String(50), default=CustomerStatus.ACTIVE.value, nullable=False, index=True
    )

    @property
    def status_enum(self) -> CustomerStatus:  # helper, not shadowing column
        try:
            return CustomerStatus(self.status)  # type: ignore[arg-type]
        except ValueError:
            return CustomerStatus.ACTIVE
