"""AuditLog model."""

from __future__ import annotations

from sqlalchemy import Column, String, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base, TenantMixin


class AuditLog(Base, TenantMixin):
    """Audit log for compliance – records mutating actions.

    Fields:
      - tenant_id (from TenantMixin)
      - actor_id: user performing action
      - action: e.g. create, update, delete, login, mfa_setup
      - resource_type: e.g. lead, customer, order, store
      - resource_id: affected resource id
      - payload_json: sanitized request payload / diff
      - ip_address: client IP
      - created_at: from Base
    """

    __tablename__ = "audit_logs"

    actor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    ip_address = Column(String(45), nullable=True)

    __table_args__ = (
        Index("idx_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("idx_audit_logs_tenant_resource", "tenant_id", "resource_type", "resource_id"),
    )
