"""Product and ProductVariant models."""

from __future__ import annotations

import enum
from sqlalchemy import (
    Boolean,
    Column,
    String,
    Text,
    Integer,
    JSON,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import synonym
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class ProductStatus(str, enum.Enum):
    """Product status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class ProductAgeSuitability(str, enum.Enum):
    """Product age suitability enum."""

    NEWBORN = "newborn"
    INFANT = "infant"
    TODDLER = "toddler"
    CHILD = "child"
    ALL = "all"


class ProductPregnancyStage(str, enum.Enum):
    """Product pregnancy/postpartum stage enum."""

    PRECONCEPTION = "preconception"
    PREGNANCY_FIRST_TRIMESTER = "pregnancy_first_trimester"
    PREGNANCY_SECOND_TRIMESTER = "pregnancy_second_trimester"
    PREGNANCY_THIRD_TRIMESTER = "pregnancy_third_trimester"
    POSTPARTUM = "postpartum"
    NEWBORN = "newborn"
    INFANT = "infant"
    TODDLER = "toddler"


class Product(Base, TenantMixin):
    """Product model.

    Products need categories, collections, variants, SKU, price,
    sale price, tax class, dimensions, inventory, images,
    ingredients/materials, safety information, age suitability
    and pregnancy/postpartum stage.
    """

    __tablename__ = "products"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True
    )
    sku = Column(String(100), unique=True, nullable=False, index=True)
    price_cents = Column(Integer, nullable=False)
    sale_price_cents = Column(Integer, nullable=True)
    tax_class = Column(String(50), default="standard", nullable=False)
    dimensions_json = Column(JSON, nullable=True)
    barcode = Column(String(100), nullable=True)
    inventory_track = Column(Boolean, default=True, nullable=False)
    inventory_quantity = Column(Integer, default=0, nullable=False)
    # Legacy 'inventory' alias for backward compat — maps to inventory_quantity (DB column)
    inventory = synonym("inventory_quantity")
    inventory_policy = Column(String(50), default="deny", nullable=False)
    visibility = Column(String(50), default="visible", nullable=False)
    tags = Column(JSON, nullable=False, default=list)
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    gallery_urls = Column(JSON, nullable=False, default=list)
    images_json = Column(JSON, nullable=False, default=list)
    ingredients = Column(Text, nullable=True)
    safety_info = Column(Text, nullable=True)
    age_suitability = Column(
        SAEnum(ProductAgeSuitability, native_enum=False, length=50), nullable=True
    )
    pregnancy_stage = Column(
        SAEnum(ProductPregnancyStage, native_enum=False, length=50), nullable=True
    )
    status = Column(
        SAEnum(ProductStatus, native_enum=False, length=50), default=ProductStatus.ACTIVE, nullable=False
    )


class ProductVariant(Base, TenantMixin):
    """Product variant model.

    Variants for different sizes, colors, etc.
    """

    __tablename__ = "product_variants"

    product_id = Column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    sku = Column(String(100), unique=True, nullable=False, index=True)
    price_cents = Column(Integer, nullable=False)
    sale_price_cents = Column(Integer, nullable=True)
    inventory = Column(Integer, default=0, nullable=False)
    dimensions_json = Column(JSON, nullable=True)
