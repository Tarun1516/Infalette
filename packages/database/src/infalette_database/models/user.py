"""User model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, Boolean, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class UserStatus(str, enum.Enum):
    """User status enum."""

    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class User(Base):
    """User model.

    Users belong to a tenant (except platform owners) and have roles
    that determine their capabilities.
    """

    __tablename__ = "users"

    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    # Clerk linkage: ``user_...`` id from Clerk. Null for legacy rows created
    # before the Clerk migration; unique when present. Webhook sync
    # (POST /api/v1/webhooks/clerk) backfills this on user.created/updated.
    clerk_user_id = Column(String(64), unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # Nullable for Clerk-managed accounts (no local password). Legacy
    # password rows always have a hash.
    password_hash = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    # Role stored as plain string (matches alembic 001 users.role);
    # values from models/role.UserRole.
    role = Column(String(50), default="tenant_owner", nullable=False, index=True)
    status = Column(
        SAEnum(UserStatus, native_enum=False, length=50), default=UserStatus.ACTIVE, nullable=False
    )
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)
    # Hashed single-use recovery codes (consumed on successful login use)
    mfa_recovery_codes_json = Column(JSON, nullable=False, default=list)
