"""Lead model."""

from __future__ import annotations

import enum
from sqlalchemy import Column, String, Integer, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import synonym
from sqlalchemy.ext.hybrid import hybrid_property

from infalette_database.base import Base, TenantMixin


class LeadStage(str, enum.Enum):
    """Lead stage enum.

    Recommended lead stages:
    New Lead → Engaged → Product Selected → Checkout Created → Paid → Fulfilled → Repeat Customer
    """

    NEW_LEAD = "new_lead"
    ENGAGED = "engaged"
    PRODUCT_SELECTED = "product_selected"
    CHECKOUT_CREATED = "checkout_created"
    PAID = "paid"
    FULFILLED = "fulfilled"
    REPEAT_CUSTOMER = "repeat_customer"
    # Legacy / service aliases
    NEW = "new"
    CONVERTED = "converted"


class LeadSource(str, enum.Enum):
    """Lead source enum."""

    INSTAGRAM_COMMENT = "instagram_comment"
    INSTAGRAM_DM = "instagram_dm"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    REFERRAL = "referral"
    INSTAGRAM = "instagram"
    IMPORT = "import"
    OTHER = "other"


class Lead(Base, TenantMixin):
    """Lead model.

    CRM leads with stage, source, campaign and assigned agent.
    "DM but did not buy" is calculated from events, not manually entered.

    Alembic (001) defines: first_name, last_name, email, phone, source(String),
    status(String), tags(JSONB), assigned_to(UUID), plus timestamps.
    This model keeps LeadStage enum (mapped to DB column `status` via synonym)
    for type safety while also exposing a plain `status` string alias for
    legacy services that read/write Lead.status as string.
    """

    __tablename__ = "leads"

    # Core identity – nullable to support alembic and service variations
    customer_id = Column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True, index=True)

    # Use String for source to allow flexible values; enum still valid for validation
    source = Column(String(100), nullable=True, index=True)

    # DB column is `status` (String). We store raw string in _status column named "status".
    # Use hybrid properties so both Lead.status and Lead.stage are queryable.
    _status = Column("status", String(50), default=LeadStage.NEW_LEAD.value, nullable=False, index=True)
    _stage = Column("stage", SAEnum(LeadStage, native_enum=False, length=50), nullable=True)  # optional typed stage column if migration adds it

    campaign_id = Column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    assigned_to = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # Alias so code using assigned_agent_id continues to work
    assigned_agent_id = synonym("assigned_to")

    # Additional fields used by services
    tags = Column(JSON, nullable=False, default=list)
    score = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSON, nullable=False, default=dict)

    # ------------------------------------------------------------------
    # stage / status aliasing (hybrid for query support)
    # ------------------------------------------------------------------
    @hybrid_property
    def status(self) -> str:
        """String status – primary DB column _status."""
        return self._status

    @status.setter
    def status(self, value) -> None:
        if isinstance(value, LeadStage):
            self._status = value.value
            self._stage = value
        elif isinstance(value, str):
            self._status = value
            try:
                self._stage = LeadStage(value)
            except ValueError:
                self._stage = None
        elif value is None:
            self._status = LeadStage.NEW_LEAD.value
            self._stage = LeadStage.NEW_LEAD
        else:
            self._status = str(value)
            self._stage = None

    @status.expression  # type: ignore[no-redef]
    def status(cls):  # pylint: disable=no-self-argument
        return cls._status

    @hybrid_property
    def stage(self) -> LeadStage | str:
        """Typed stage view – prefers _stage else converts _status."""
        if self._stage is not None:
            return self._stage
        raw = self._status
        if raw is None:
            return LeadStage.NEW_LEAD
        try:
            return LeadStage(raw)
        except ValueError:
            return raw

    @stage.setter
    def stage(self, value) -> None:
        if isinstance(value, LeadStage):
            self._status = value.value
            self._stage = value
        elif isinstance(value, str):
            try:
                enum_val = LeadStage(value)
                self._status = enum_val.value
                self._stage = enum_val
            except ValueError:
                self._status = value
                self._stage = None
        elif value is None:
            self._status = LeadStage.NEW_LEAD.value
            self._stage = LeadStage.NEW_LEAD
        else:
            self._status = str(value)
            self._stage = None

    @stage.expression  # type: ignore[no-redef]
    def stage(cls):  # pylint: disable=no-self-argument
        # For SQL queries, prefer _stage if not null else _status comparison
        # We expose _status as stage expression; enum vs string两者都可通过 string filter
        return cls._status

    # ------------------------------------------------------------------
    # Compatibility shims for legacy attribute names
    # ------------------------------------------------------------------
    @property
    def assigned_agent(self):  # pragma: no cover
        return self.assigned_to

    @assigned_agent.setter
    def assigned_agent(self, val):  # pragma: no cover
        self.assigned_to = val
