"""Add discount_codes table.

Revision ID: 002_add_discount_codes
Revises: 001_initial_schema
Create Date: 2024-02-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "002_add_discount_codes"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discount_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("minimum_order_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("usage_limit", sa.Integer, nullable=True),
        sa.Column("used_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_discount_codes_tenant_code"),
    )
    op.create_index("ix_discount_codes_code", "discount_codes", ["code"])
    # NOTE: ix_discount_codes_tenant_id is auto-created by `index=True`
    # on the tenant_id column above. Creating it again here raises
    # DuplicateTableError against a fresh database.


def downgrade() -> None:
    op.drop_index("ix_discount_codes_tenant_id", table_name="discount_codes")
    op.drop_index("ix_discount_codes_code", table_name="discount_codes")
    op.drop_table("discount_codes")
