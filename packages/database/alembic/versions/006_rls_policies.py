"""Enable row-level security with a safe, default-open tenant isolation policy.

GUC contract
------------
The policy reads the per-connection GUC `app.current_tenant_id`. Apps that
want hard isolation opt in per transaction with:

    SET LOCAL app.current_tenant_id = '<tenant uuid>';

`SET LOCAL` is scoped to the transaction, so pooled connections never leak a
stale tenant id. When the GUC is unset (empty string), NULLIF turns it into
NULL and COALESCE falls back to `tenant_id = tenant_id`, which is always true —
i.e. the policy is a no-op and behavior is unchanged until the app opts in.
Once the GUC is set, only rows for that tenant are visible.

Every statement is idempotent: policies are dropped first (DROP POLICY IF
EXISTS) before creation, so re-running this migration is safe.

Revision ID: 006_rls_policies
Revises: 005_campaigns
Create Date: 2026-08-22
"""

from alembic import op

revision = "006_rls_policies"
down_revision = "005_campaigns"
branch_labels = None
depends_on = None

# Every tenant-scoped table (tenants itself excluded).
TENANT_TABLES = [
    "stores",
    "products",
    "product_variants",
    "categories",
    "collections",
    "customers",
    "carts",
    "cart_items",
    "checkouts",
    "checkout_items",
    "orders",
    "order_items",
    "payments",
    "refunds",
    "fulfillments",
    "leads",
    "conversations",
    "messages",
    "social_identities",
    "automation_rules",
    "automation_actions",
    "integrations",
    "webhooks",
    "webhook_deliveries",
    "pages",
    "seo_pages",
    "subscriptions",
    "discount_codes",
    "audit_logs",
    "events",
    "metrics_daily",
    "campaigns",
    "domains",
    "themes",
    "seo_redirects",
    # Users carry a nullable tenant_id; RLS enforces it when set.
    "users",
]

# Child tables that predate the TenantMixin convention: they only carry a
# parent FK. Give them a real tenant_id column (backfilled from the parent)
# so row-level security can enforce isolation directly on these rows too.
_CHILD_TENANT_COLUMNS = [
    # (table, column, parent table, parent join key)
    ("cart_items", "cart_id", "carts"),
    ("checkout_items", "checkout_id", "checkouts"),
    ("order_items", "order_id", "orders"),
    ("messages", "conversation_id", "conversations"),
    ("refunds", "payment_id", "payments"),
    ("fulfillments", "order_id", "orders"),
    ("automation_actions", "rule_id", "automation_rules"),
    ("webhook_deliveries", "endpoint_id", "webhooks"),
]


def upgrade() -> None:
    for table, fk_col, parent in _CHILD_TENANT_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id UUID"
        )
        # Some child FKs (e.g. webhook_deliveries.endpoint_id) are added by a
        # later migration; only backfill when the FK column already exists.
        op.execute(
            f"DO $$ BEGIN "
            f"IF EXISTS (SELECT 1 FROM information_schema.columns "
            f"           WHERE table_name='{table}' AND column_name='{fk_col}') THEN "
            f"UPDATE {table} c SET tenant_id = p.tenant_id "
            f"FROM {parent} p WHERE c.{fk_col} = p.id AND c.tenant_id IS NULL; "
            f"END IF; END $$"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {table} (tenant_id)"
        )
    # webhook_deliveries may also be linked via the legacy webhook_id column.
    op.execute(
        "UPDATE webhook_deliveries d SET tenant_id = w.tenant_id "
        "FROM webhooks w WHERE d.webhook_id = w.id AND d.tenant_id IS NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users (tenant_id)")

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        # COALESCE(NULLIF(GUC, '')::uuid, tenant_id) passes when GUC unset
        # (zero behavior change) and enforces tenant match when set.
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING ("
            f"tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', true), '')::uuid, tenant_id))"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table, _, __ in _CHILD_TENANT_COLUMNS:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id")
