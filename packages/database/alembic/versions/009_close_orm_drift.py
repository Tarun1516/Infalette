"""Close ORM↔migration drift found in the v6 audit.

Adds every column the ORM maps (or services write) that no earlier
migration created. All statements use IF NOT EXISTS / guarded adds so
re-runs are safe.

Fixes:
- stores: logo_url, currency, tax_rate (theme_config + custom_domain
  already exist from 001 but were never mapped by the ORM — mapping is
  an ORM change, no DDL needed)
- products: category_id FK
- categories: seo_title, seo_description, sort_order, status
- collections: name, description, sort_order, status, seo_title,
  seo_description, rules JSONB
- leads: stage (mapped by ORM as ``_stage``; hybrid setter always writes)
- customers: metadata_json
- conversations: customer_id, assigned_to, metadata_json

Revision ID: 009_close_orm_drift
Revises: 008_report_schedules
Create Date: 2026-08-24
"""

from alembic import op

revision = "009_close_orm_drift"
down_revision = "008_report_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- stores: settings the admin UI persists -------------------------
    op.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500)")
    op.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'INR'")
    op.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS tax_rate INTEGER DEFAULT 0")

    # --- products: category linkage -------------------------------------
    op.execute(
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES categories(id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_category_id ON products (category_id)")

    # --- categories: merchandising fields the service writes ------------
    op.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS seo_title VARCHAR(255)")
    op.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS seo_description TEXT")
    op.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0")
    op.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active'")

    # --- collections: full merchandising surface ------------------------
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS name VARCHAR(255)")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active'")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS seo_title VARCHAR(255)")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS seo_description TEXT")
    op.execute("ALTER TABLE collections ADD COLUMN IF NOT EXISTS rules JSONB DEFAULT '[]'::jsonb")

    # --- leads: ORM maps a nullable `stage` column and writes it --------
    # ORM declares it as SAEnum(LeadStage); create the enum type if absent,
    # then the column using it (VARCHAR fallback handled by CAST below).
    op.execute("DO $$ BEGIN CREATE TYPE leadstage AS ENUM ('new_lead', 'new', 'engaged', 'product_selected', 'checkout_created', 'paid', 'fulfilled', 'repeat_customer', 'converted'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute(
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS stage LEADSTAGE"
    )

    # --- customers: free-form metadata used by services ------------------
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS metadata_json JSONB DEFAULT '{}'::jsonb"
    )

    # --- conversations: CRM linkage --------------------------------------
    op.execute(
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)"
    )
    op.execute(
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES users(id)"
    )
    op.execute(
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS metadata_json JSONB DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    # Columns are additive; dropping them would lose data. Left as no-op.
    pass
