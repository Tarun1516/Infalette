"""SocialIdentity model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import synonym

from infalette_database.base import Base, TenantMixin
from infalette_database.types import EncryptedString


class SocialIdentity(Base, TenantMixin):
    """Social identity model.

    Two roles, one table:
    - Tenant channel connection: the influencer's own Instagram/WhatsApp
      OAuth tokens (``customer_id`` NULL).
    - Shopper channel identity: a customer's Instagram/WhatsApp handle
      (``customer_id`` set) so people can be unified across channels
      where identity can be lawfully matched (spec §7).
    """

    __tablename__ = "social_identities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_user_id",
            name="uq_social_identity_tenant_provider_user",
        ),
        Index("ix_social_identities_tenant_provider", "tenant_id", "provider"),
    )

    provider = Column(String(50), nullable=False, index=True)
    provider_user_id = Column(String(255), nullable=True, index=True)
    # OAuth tokens encrypted at rest (Fernet key derived from SECRET_KEY)
    access_token = Column(EncryptedString(), nullable=True)
    refresh_token = Column(EncryptedString(), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="active", server_default="active")
    # Shopper link: set when this identity belongs to a customer profile
    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )

    # Backward-compat aliases: allow queries/attribute access via legacy names
    # platform -> provider, platform_id -> provider_user_id
    platform = synonym("provider")
    platform_id = synonym("provider_user_id")
    # Encrypted alias (historical used EncryptedString)
    access_token_encrypted = synonym("access_token")
    refresh_token_encrypted = synonym("refresh_token")
