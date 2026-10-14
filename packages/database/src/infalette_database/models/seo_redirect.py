"""SEO redirect model (301/302 URL redirects per tenant)."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class SeoRedirect(Base, TenantMixin):
    """Tenant-scoped URL redirect (old_path -> new_path)."""

    __tablename__ = "seo_redirects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "old_path", name="uq_seo_redirect_tenant_old_path"),
    )

    old_path = Column(String(500), nullable=False, index=True)
    new_path = Column(String(500), nullable=False)
    status_code = Column(Integer, default=301, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
