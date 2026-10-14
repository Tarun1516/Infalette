"""Domain model."""

from __future__ import annotations

from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class Domain(Base, TenantMixin):
    """Domain model.

    Each tenant can have custom domains and subdomains.
    """

    __tablename__ = "domains"

    domain = Column(String(255), unique=True, nullable=False, index=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
