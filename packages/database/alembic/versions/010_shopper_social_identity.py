"""Shopper-level social identity linking (spec §7: SocialIdentity = Customer
plus Instagram/WhatsApp channel identity).

Adds ``social_identities.customer_id`` so a shopper's Instagram/WhatsApp
handle can be unified with their website customer profile, plus an index
for webhook-time lookups by (tenant, provider, provider_user_id).

Revision ID: 010_shopper_social_identity
Revises: 009_close_orm_drift
Create Date: 2026-08-24
"""

from alembic import op

revision = "010_shopper_social_identity"
down_revision = "009_close_orm_drift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE social_identities ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_social_identities_customer_id ON social_identities (customer_id)"
    )


def downgrade() -> None:
    # Additive column; left in place on downgrade to avoid data loss.
    pass
