"""Collection model."""

from __future__ import annotations

from sqlalchemy import Column, String, Text, JSON, Integer

from infalette_database.base import Base, TenantMixin


class Collection(Base, TenantMixin):
    """Collection model.

    Curated groups of products.
    """

    __tablename__ = "collections"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    product_ids_json = Column("product_ids", JSON, nullable=False, default=list)
    status = Column(String(50), default="active", nullable=True)
    sort_order = Column(Integer, default=0, nullable=True)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    rules = Column(JSON, nullable=False, default=list)

    # Alias retained for code that reads ``product_ids``
    @property
    def product_ids(self) -> list:
        return self.product_ids_json or []

    @product_ids.setter
    def product_ids(self, value: list) -> None:
        self.product_ids_json = value or []
