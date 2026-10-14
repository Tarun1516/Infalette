"""Add missing tables used by ORM models but absent from 001.

Creates: domains, themes, roles, product_variants, order_items,
checkout_items, fulfillments, refunds. Adds carts.session_key for
guest carts and customers.metadata_json + social_identities unique index.

Revision ID: 004_missing_tables
Revises: 003_add_audit_logs
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_missing_tables"
down_revision = "003_add_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Domains (custom domain per tenant)
    op.create_table(
        "domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("domain", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Themes (design tokens / presets per tenant)
    op.create_table(
        "themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Roles (RBAC)
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("permissions_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute(
        "INSERT INTO roles (name) VALUES ('platform_owner'),('tenant_owner'),"
        "('store_manager'),('marketing_agent'),('support_agent'),('customer') "
        "ON CONFLICT (name) DO NOTHING"
    )

    # Product variants
    op.create_table(
        "product_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("sku", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("sale_price_cents", sa.Integer),
        sa.Column("inventory_quantity", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("inventory", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("dimensions_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Order items (immutable snapshots)
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.id")),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("product_snapshot_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Checkout items (immutable snapshots)
    op.create_table(
        "checkout_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checkouts.id"), nullable=False, index=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.id")),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("product_snapshot_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Fulfillments (shipment tracking)
    op.create_table(
        "fulfillments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("tracking_number", sa.String(255)),
        sa.Column("carrier", sa.String(100)),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Refunds
    op.create_table(
        "refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False, index=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("reason", sa.Text),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Guest cart sessions
    op.execute("ALTER TABLE carts ADD COLUMN IF NOT EXISTS session_key VARCHAR(64)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_carts_session_key ON carts (session_key)")

    # Customer metadata (consent/timeline extras)
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS metadata_json JSONB "
        "DEFAULT '{}'::jsonb"
    )

    # Social identity uniqueness per tenant+provider+user
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_social_identity_provider_user "
        "ON social_identities (tenant_id, provider, provider_user_id)"
    )


def downgrade() -> None:
    op.drop_index("uq_social_identity_provider_user", table_name="social_identities")
    op.drop_column("customers", "metadata_json")
    op.drop_column("carts", "session_key")
    op.drop_table("refunds")
    op.drop_table("fulfillments")
    op.drop_table("checkout_items")
    op.drop_table("order_items")
    op.drop_table("product_variants")
    op.drop_table("roles")
    op.drop_table("themes")
    op.drop_table("domains")
