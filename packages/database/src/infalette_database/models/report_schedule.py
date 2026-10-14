"""ReportSchedule model — scheduled CSV exports (CRM plan entitlement)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String

from infalette_database.base import Base, TenantMixin


class ReportSchedule(Base, TenantMixin):
    """A tenant-configured recurring data export.

    report_type: orders | customers | leads
    frequency: daily | weekly
    recipients_json: list of email addresses receiving the CSV link/body.
    """

    __tablename__ = "report_schedules"

    name = Column(String(255), nullable=False, default="")
    report_type = Column(String(50), nullable=False)
    frequency = Column(String(20), nullable=False, default="daily")
    recipients_json = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, nullable=False, default=0)
