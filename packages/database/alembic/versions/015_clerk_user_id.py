"""Link local users to Clerk identities.

Adds ``users.clerk_user_id`` (nullable, unique) and relaxes
``users.password_hash`` to nullable so Clerk-managed accounts can exist
without a local password. Legacy password rows are untouched.

Idempotent: safe to re-run on Neon or local Postgres.

Revision ID: 015_clerk_user_id
Revises: 014_cart_items_updated_at
Create Date: 2026-09-07
"""

from alembic import op

revision = "015_clerk_user_id"
down_revision = "014_cart_items_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(64)"
    )
    # Unique index only for non-null values (Postgres treats NULLs as
    # distinct, so legacy rows with NULL never conflict).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_clerk_user_id "
        "ON users (clerk_user_id)"
    )
    op.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")


def downgrade() -> None:
    # Only null out the link; keep password_hash nullable to avoid breaking
    # Clerk-managed rows that may already exist.
    op.execute("DROP INDEX IF EXISTS ix_users_clerk_user_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS clerk_user_id")
