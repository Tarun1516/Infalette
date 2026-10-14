"""Integration model."""

from __future__ import annotations

from sqlalchemy import Column, String
from sqlalchemy import JSON

from infalette_database.base import Base, TenantMixin


class Integration(Base, TenantMixin):
    """Tenant-level third-party integration credentials.

    Stores per-tenant connected accounts (e.g. Razorpay route /
    Stripe Connect linked merchant accounts) used to route funds.
    """

    __tablename__ = "integrations"

    provider = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="disconnected", nullable=False)
    credentials_json = Column(JSON, default=dict)
    config_json = Column(JSON, default=dict)
