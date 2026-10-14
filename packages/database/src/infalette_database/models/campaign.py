"""Campaign model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, DateTime, String

from infalette_database.base import Base, TenantMixin


class CampaignStatus(str, enum.Enum):
    """Campaign lifecycle status."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Campaign(Base, TenantMixin):
    """Marketing campaign model.

    Tracks UTM-attributed campaigns (Instagram / WhatsApp / website)
    so leads and orders can be attributed to a source campaign.
    """

    __tablename__ = "campaigns"

    name = Column(String(255), nullable=False)
    slug = Column(String(255), index=True)
    source = Column(String(50))  # instagram | whatsapp | website
    utm_source = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)
    status = Column(String(50), default=CampaignStatus.ACTIVE.value, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
