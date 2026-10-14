"""Immutable tax snapshot on order items (spec §7).

Adds order_items.tax_cents / order_items.tax_rate_bps so invoices use
the tax captured at checkout instead of recomputing from current rates.

Revision ID: 012_order_item_tax_snapshot
Revises: 011_close_drift
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa


revision = "012_order_item_tax_snapshot"
down_revision = "011_close_drift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("tax_cents", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("tax_rate_bps", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "tax_rate_bps")
    op.drop_column("order_items", "tax_cents")
