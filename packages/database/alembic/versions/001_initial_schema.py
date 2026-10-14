"""Initial schema migration.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extension for UUID
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    # Tenants
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("plan", sa.String(50), default="store"),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Plans
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), default="INR"),
        sa.Column("interval", sa.String(20), default="month"),
        sa.Column("features_json", postgresql.JSONB, default=dict),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("role", sa.String(50), default="tenant_owner"),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("mfa_enabled", sa.Boolean, default=False),
        sa.Column("mfa_secret", sa.String(255)),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Stores
    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("theme_config", postgresql.JSONB, default=dict),
        sa.Column("custom_domain", sa.String(255)),
        sa.Column("shipping_rules_json", postgresql.JSONB, default=dict),
        sa.Column("menus_json", postgresql.JSONB, default=list),
        sa.Column("social_links_json", postgresql.JSONB, default=dict),
        sa.Column("legal_pages_json", postgresql.JSONB, default=dict),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("sale_price_cents", sa.Integer),
        sa.Column("sku", sa.String(100), unique=True),
        sa.Column("barcode", sa.String(100)),
        sa.Column("inventory_track", sa.Boolean, default=True),
        sa.Column("inventory_quantity", sa.Integer, default=0),
        sa.Column("inventory_policy", sa.String(50), default="deny"),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("visibility", sa.String(50), default="visible"),
        sa.Column("tags", postgresql.JSONB, default=list),
        sa.Column("meta_title", sa.String(255)),
        sa.Column("meta_description", sa.Text),
        sa.Column("image_url", sa.String(500)),
        sa.Column("gallery_urls", postgresql.JSONB, default=list),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Categories
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id")),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Collections
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("product_ids", postgresql.JSONB, default=list),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Customers
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("phone", sa.String(20)),
        sa.Column("tags", postgresql.JSONB, default=list),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Carts
    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("total_cents", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Cart Items
    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Checkouts
    op.create_table(
        "checkouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id")),
        sa.Column("items_json", postgresql.JSONB, default=list),
        sa.Column("discounts_json", postgresql.JSONB, default=list),
        sa.Column("total_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), default="INR"),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("attribution_json", postgresql.JSONB, default=dict),
        sa.Column("expires_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Orders
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checkouts.id")),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("total_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), default="INR"),
        sa.Column("shipping_address_json", postgresql.JSONB, default=dict),
        sa.Column("billing_address_json", postgresql.JSONB, default=dict),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Payments
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checkouts.id")),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_payment_id", sa.String(255)),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), default="INR"),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("method", sa.String(50)),
        sa.Column("metadata_json", postgresql.JSONB, default=dict),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Leads
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(20)),
        sa.Column("source", sa.String(100)),
        sa.Column("status", sa.String(50), default="new"),
        sa.Column("tags", postgresql.JSONB, default=list),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("channel", sa.String(50)),
        sa.Column("external_id", sa.String(255)),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("direction", sa.String(50)),
        sa.Column("content", sa.Text),
        sa.Column("external_id", sa.String(255)),
        sa.Column("status", sa.String(50), default="sent"),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Events
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", postgresql.JSONB, default=dict),
        sa.Column("request_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Metrics Daily
    op.create_table(
        "metrics_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric),
        sa.Column("metadata_json", postgresql.JSONB, default=dict),
    )

    # Social Identities
    op.create_table(
        "social_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255)),
        sa.Column("access_token", sa.Text),
        sa.Column("refresh_token", sa.Text),
        sa.Column("expires_at", sa.DateTime),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Automation Rules
    op.create_table(
        "automation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("trigger_type", sa.String(100)),
        sa.Column("trigger_config", postgresql.JSONB, default=dict),
        sa.Column("conditions", postgresql.JSONB, default=list),
        sa.Column("status", sa.String(50), default="draft"),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Automation Actions
    op.create_table(
        "automation_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("automation_rules.id"), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("config", postgresql.JSONB, default=dict),
        sa.Column("order", sa.Integer, default=0),
    )

    # Integrations
    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), default="disconnected"),
        sa.Column("credentials_json", postgresql.JSONB, default=dict),
        sa.Column("config_json", postgresql.JSONB, default=dict),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Webhooks
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("events", postgresql.JSONB, default=list),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("secret", sa.String(255)),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # Webhook Deliveries
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("webhooks.id"), nullable=False),
        sa.Column("event_type", sa.String(100)),
        sa.Column("payload_json", postgresql.JSONB, default=dict),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("response_status", sa.Integer),
        sa.Column("response_body", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime),
    )

    # Pages
    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255)),
        sa.Column("blocks_json", postgresql.JSONB, default=list),
        sa.Column("status", sa.String(50), default="draft"),
        sa.Column("is_homepage", sa.Boolean, default=False),
        sa.Column("meta_title", sa.String(255)),
        sa.Column("meta_description", sa.Text),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )

    # SEO Pages
    op.create_table(
        "seo_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("url_path", sa.String(500), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("meta_description", sa.Text),
        sa.Column("meta_keywords", sa.Text),
        sa.Column("canonical_url", sa.String(500)),
        sa.Column("robots_index", sa.Boolean, default=True, nullable=False),
        sa.Column("robots_follow", sa.Boolean, default=True, nullable=False),
        sa.Column("structured_data", postgresql.JSONB, default=dict),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )
    op.create_index("ix_seo_pages_tenant_id", "seo_pages", ["tenant_id"])
    op.create_index("ix_seo_pages_url_path", "seo_pages", ["url_path"])

    # SEO Redirects (301/302 per tenant)
    op.create_table(
        "seo_redirects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("old_path", sa.String(500), nullable=False),
        sa.Column("new_path", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer, default=301, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "old_path", name="uq_seo_redirect_tenant_old_path"),
    )
    op.create_index("ix_seo_redirects_tenant_id", "seo_redirects", ["tenant_id"])
    op.create_index("ix_seo_redirects_old_path", "seo_redirects", ["old_path"])

    # Subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id")),
        sa.Column("status", sa.String(50), default="active"),
        sa.Column("current_period_start", sa.DateTime),
        sa.Column("current_period_end", sa.DateTime),
        sa.Column("cancelled_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("seo_redirects")
    op.drop_table("seo_pages")
    op.drop_table("pages")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("integrations")
    op.drop_table("automation_actions")
    op.drop_table("automation_rules")
    op.drop_table("social_identities")
    op.drop_table("metrics_daily")
    op.drop_table("events")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("leads")
    op.drop_table("payments")
    op.drop_table("orders")
    op.drop_table("checkouts")
    op.drop_table("cart_items")
    op.drop_table("carts")
    op.drop_table("customers")
    op.drop_table("collections")
    op.drop_table("categories")
    op.drop_table("products")
    op.drop_table("stores")
    op.drop_table("users")
    op.drop_table("plans")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
