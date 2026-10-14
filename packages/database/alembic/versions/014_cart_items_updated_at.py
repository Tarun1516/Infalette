"""Close cart_items / messages / events drift.

Migration 001 omitted ``updated_at`` on three tables whose models inherit
the column from the declarative Base:

  * cart_items  - read by /api/v1/cart/* (cart and checkout flows)
  * messages    - conversation timeline
  * events      - audit / analytics pipeline

Every read therefore raised ``UndefinedColumnError: column X.updated_at
does not exist`` as soon as a real workload hit Postgres. This revision
backfills the column on existing rows (NULL -> created_at to satisfy the
NOT NULL constraint) and adds it to the schema. Idempotent: re-running
on an up-to-date database is a no-op.

Revision ID: 014_cart_items_updated_at
Revises: 013_plans_updated_at
Create Date: 2026-09-01
"""

from alembic import op

revision = "014_cart_items_updated_at"
down_revision = "013_plans_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("cart_items", "messages", "events"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"
        )
        op.execute(
            f"UPDATE {table} SET updated_at = created_at WHERE updated_at IS NULL"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN updated_at SET NOT NULL"
        )


def downgrade() -> None:
    for table in ("cart_items", "messages", "events"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS updated_at")
