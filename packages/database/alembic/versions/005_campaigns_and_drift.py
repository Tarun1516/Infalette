"""Add campaigns table and schema drift fixes.

Creates the campaigns table (matching infalette_database.models.campaign.Campaign)
and backfills columns that exist on ORM models but were missing from earlier
migrations: leads (customer_id, campaign_id, score, metadata_json),
customers (addresses_json, consent_json), stores (description, theme_id,
published_at). Drift fixes use ADD COLUMN IF NOT EXISTS so re-runs are safe.

Revision ID: 005_campaigns
Revises: 004_missing_tables
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_campaigns"
down_revision = "004_missing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Campaigns (marketing attribution)
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), index=True),
        sa.Column("source", sa.String(50)),
        sa.Column("utm_source", sa.String(255)),
        sa.Column("utm_medium", sa.String(255)),
        sa.Column("utm_campaign", sa.String(255)),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ------------------------------------------------------------------
    # Schema drift fixes vs ORM models (idempotent, safe to re-run).
    # ------------------------------------------------------------------

    # Leads: campaign attribution + scoring + free-form metadata.
    # Note: leads.customer_id may already exist from 001; IF NOT EXISTS keeps this idempotent.
    op.execute(
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)"
    )
    op.execute(
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES campaigns(id)"
    )
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS score INTEGER DEFAULT 0")
    op.execute(
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata_json JSONB DEFAULT '{}'::jsonb"
    )

    # Customers: addresses and marketing consent as JSON documents.
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS addresses_json JSONB DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS consent_json JSONB DEFAULT '{}'::jsonb"
    )

    # Stores: storefront copy + theme link + publish timestamp.
    op.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute(
        "ALTER TABLE stores ADD COLUMN IF NOT EXISTS theme_id UUID REFERENCES themes(id)"
    )
    op.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ")


def downgrade() -> None:
    # Leave drift-fix columns in place; only drop the new table.
    op.drop_table("campaigns")
