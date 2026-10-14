"""Store model."""

from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON

from infalette_database.base import Base, TenantMixin


class StoreStatus(str, enum.Enum):
    """Store status enum."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Store(Base, TenantMixin):
    """Store model.

    Each tenant has one store with theme, pages, catalog,
    payment and shipping settings.
    """

    __tablename__ = "stores"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    theme_id = Column(
        UUID(as_uuid=True), ForeignKey("themes.id"), nullable=True
    )
    theme_config = Column(JSON, default=dict, nullable=True)
    custom_domain = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    currency = Column(String(3), default="INR", nullable=True)
    tax_rate = Column(Integer, default=0, nullable=True)
    # Tenant-configurable commerce settings (spec §3 tenant management)
    shipping_rules_json = Column(JSON, default=dict, nullable=True)
    menus_json = Column(JSON, default=list, nullable=True)
    social_links_json = Column(JSON, default=dict, nullable=True)
    legal_pages_json = Column(JSON, default=dict, nullable=True)
    status = Column(
        SAEnum(StoreStatus, native_enum=False, length=50), default=StoreStatus.DRAFT, nullable=False
    )
    published_at = Column(DateTime(timezone=True), nullable=True)
