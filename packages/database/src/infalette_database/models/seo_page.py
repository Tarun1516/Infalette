"""SEO page metadata model."""

from __future__ import annotations

import enum
from sqlalchemy import JSON, Boolean, Column, String, Text
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class SeoPage(Base, TenantMixin):
    """Per-URL SEO metadata managed by tenants."""

    __tablename__ = "seo_pages"

    url_path = Column(String(500), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(Text, nullable=True)
    canonical_url = Column(String(500), nullable=True)
    robots_index = Column(Boolean, default=True, nullable=False)
    robots_follow = Column(Boolean, default=True, nullable=False)
    structured_data = Column(JSON, default=dict, nullable=False)
