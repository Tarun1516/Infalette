"""Page model."""

from __future__ import annotations

import enum
from sqlalchemy import Boolean, Column, String, Text, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class PageStatus(str, enum.Enum):
    """Page status enum."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PageBlockType(str, enum.Enum):
    """Page block type enum."""

    HERO = "hero"
    FEATURED_PRODUCTS = "featured_products"
    CATEGORY_GRID = "category_grid"
    TESTIMONIALS = "testimonials"
    INFLUENCER_STORY = "influencer_story"
    VIDEO = "video"
    FAQ = "faq"
    BUNDLES = "bundles"
    NEWSLETTER = "newsletter"
    INSTAGRAM_GALLERY = "instagram_gallery"


class Page(Base, TenantMixin):
    """Page model.

    Storefront pages using controlled blocks. Clients configure
    the blocks but cannot insert arbitrary code.
    """

    __tablename__ = "pages"

    store_id = Column(
        UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True, index=True
    )
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    path = Column(String(255), nullable=True, index=True)
    blocks_json = Column(JSON, nullable=False, default=list)
    status = Column(
        SAEnum(PageStatus, native_enum=False, length=50), default=PageStatus.DRAFT, nullable=False
    )
    is_homepage = Column(Boolean, default=False, nullable=False)
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
