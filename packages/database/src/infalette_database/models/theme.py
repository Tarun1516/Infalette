"""Theme model."""

from __future__ import annotations

from sqlalchemy import Column, String, JSON, Boolean

from infalette_database.base import Base, TenantMixin


class Theme(Base, TenantMixin):
    """Theme model.

    Design tokens and theme presets that can be configured into
    genuinely different storefronts.
    """

    __tablename__ = "themes"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    config_json = Column(JSON, nullable=False, default=dict)
    is_default = Column(Boolean, default=False, nullable=False)
