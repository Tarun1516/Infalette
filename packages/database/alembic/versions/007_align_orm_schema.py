"""Align database schema with ORM models.

Adds every ORM-only column that application code writes so the Postgres
migration path matches ``Base.metadata.create_all`` used by tests:

- products: tax_class, ingredients, safety_info, age_suitability,
  pregnancy_stage, dimensions_json, images_json
- tenants: plan_id
- carts: currency
- pages: path
- collections: product_ids_json
- conversations: lead_id, participants_json
- messages: sender_id, attachments_json
- automation_rules: conditions_json, actions_json, execution_limit
- plans: plan_type, features_json
- webhook_deliveries: endpoint_id (service-facing FK alias), delivered_at

All statements use ADD COLUMN IF NOT EXISTS so re-runs are safe.

Revision ID: 007_align_orm_schema
Revises: 006_rls_policies
Create Date: 2026-08-23
"""

from alembic import op

revision = "007_align_orm_schema"
down_revision = "006_rls_policies"
branch_labels = None
depends_on = None


_ADDS = [
    ("users", "mfa_recovery_codes_json", "JSONB DEFAULT '[]'::jsonb"),
    ("products", "tax_class", "VARCHAR(50)"),
    ("products", "ingredients", "TEXT"),
    ("products", "safety_info", "TEXT"),
    ("products", "age_suitability", "VARCHAR(100)"),
    ("products", "pregnancy_stage", "VARCHAR(100)"),
    ("products", "dimensions_json", "JSONB DEFAULT '{}'::jsonb"),
    ("products", "images_json", "JSONB DEFAULT '[]'::jsonb"),
    ("tenants", "plan_id", "UUID REFERENCES plans(id)"),
    ("carts", "currency", "VARCHAR(3) DEFAULT 'INR'"),
    ("pages", "path", "VARCHAR(255)"),
    ("collections", "product_ids", "JSONB DEFAULT '[]'::jsonb"),
    ("conversations", "lead_id", "UUID REFERENCES leads(id)"),
    ("conversations", "participants_json", "JSONB DEFAULT '[]'::jsonb"),
    ("messages", "sender_id", "UUID"),
    ("messages", "attachments_json", "JSONB DEFAULT '[]'::jsonb"),
    ("automation_rules", "conditions_json", "JSONB DEFAULT '{}'::jsonb"),
    ("automation_rules", "actions_json", "JSONB DEFAULT '[]'::jsonb"),
    ("automation_rules", "execution_limit", "INTEGER"),
    ("plans", "plan_type", "VARCHAR(50)"),
    ("plans", "features_json", "JSONB DEFAULT '{}'::jsonb"),
    ("webhook_deliveries", "endpoint_id", "UUID REFERENCES webhooks(id)"),
    ("webhook_deliveries", "response_code", "INTEGER"),
    ("webhook_deliveries", "delivered_at", "TIMESTAMPTZ"),
]


def upgrade() -> None:
    for table, column, coltype in _ADDS:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_lead_id "
        "ON conversations (lead_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_endpoint_id "
        "ON webhook_deliveries (endpoint_id)"
    )


def downgrade() -> None:
    for table, column, _ in reversed(_ADDS):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")
