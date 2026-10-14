"""Close remaining ORM/migration drift.

- metrics_daily composite indexes (ORM-only until now)
- social_identities composite unique + index matching the ORM constraint names
- users.tenant_id index

Revision ID: 011_close_drift
Revises: 010_shopper_social_identity
Create Date: 2026-08-26
"""

from alembic import op

revision = "011_close_drift"
down_revision = "010_shopper_social_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_social_identity_tenant_provider_user "
        "ON social_identities (tenant_id, provider, provider_user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_social_identities_tenant_provider "
        "ON social_identities (tenant_id, provider)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users (tenant_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_metrics_daily_tenant_date "
        "ON metrics_daily (tenant_id, date)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_daily_tenant_date_metric "
        "ON metrics_daily (tenant_id, date, metric_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_metrics_daily_tenant_date_metric")
    op.execute("DROP INDEX IF EXISTS idx_metrics_daily_tenant_date")
    op.execute("DROP INDEX IF EXISTS ix_users_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_social_identities_tenant_provider")
    op.execute("DROP INDEX IF EXISTS uq_social_identity_tenant_provider_user")
