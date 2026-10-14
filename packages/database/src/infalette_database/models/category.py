"""Category model."""

from __future__ import annotations

from sqlalchemy import Column, String, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class Category(Base, TenantMixin):
    """Category model.

    Product categories with hierarchical support (parent_id).
    """

    __tablename__ = "categories"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    parent_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True
    )
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=True)
    status = Column(String(50), default="active", nullable=True)
