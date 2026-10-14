"""Close plans.updated_at drift.

The ``plans`` table was created in 001 without an ``updated_at`` column
but every model in this codebase inherits it from the declarative Base.
The seed script and several ORM queries reference it, so a fresh
database raises ``UndefinedColumnError: column plans.updated_at does
not exist``.

This revision backfills the column on existing rows (NULL -> created_at
so the NOT NULL constraint is satisfied) and adds it to the schema.
Idempotent: re-running on an up-to-date database is a no-op.

Revision ID: 013_plans_updated_at
Revises: 012_order_item_tax_snapshot
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = "013_plans_updated_at"
down_revision = "012_order_item_tax_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE plans ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"
    )
    op.execute(
        "UPDATE plans SET updated_at = created_at WHERE updated_at IS NULL"
    )
    op.execute(
        "ALTER TABLE plans ALTER COLUMN updated_at SET NOT NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS updated_at")
