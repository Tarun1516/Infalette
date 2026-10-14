"""AutomationAction model.

Matches the ``automation_actions`` table created in alembic migration 001.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from infalette_database.base import Base


class AutomationAction(Base):
    """An ordered action attached to an AutomationRule."""

    __tablename__ = "automation_actions"

    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("automation_rules.id"),
        nullable=False,
        index=True,
    )
    action_type = Column(String(100), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    order = Column(Integer, default=0, nullable=False)
