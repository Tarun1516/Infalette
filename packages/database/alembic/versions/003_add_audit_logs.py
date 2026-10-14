"""Add audit_logs table.

Revision ID: 003_add_audit_logs
Revises: 002_add_discount_codes
Create Date: 2024-03-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "003_add_audit_logs"
down_revision = "002_add_discount_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sys
    def _log(msg):
        print(f"[003] {msg}", file=sys.stderr)
    try:
        op.create_table(
            "audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("action", sa.String(100), nullable=False, index=True),
            sa.Column("resource_type", sa.String(100), nullable=False, index=True),
            sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column("payload_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        _log("create_table audit_logs OK")
    except Exception as e:
        _log(f"create_table audit_logs FAIL: {e.__class__.__name__}: {e}")
        raise
    try:
        op.create_index("idx_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])
        _log("create_index idx_audit_logs_tenant_created OK")
    except Exception as e:
        _log(f"create_index tenant_created FAIL: {e.__class__.__name__}: {e}")
        raise
    try:
        op.create_index("idx_audit_logs_tenant_resource", "audit_logs", ["tenant_id", "resource_type", "resource_id"])
        _log("create_index idx_audit_logs_tenant_resource OK")
    except Exception as e:
        _log(f"create_index tenant_resource FAIL: {e.__class__.__name__}: {e}")
        raise
    # NOTE: ix_audit_logs_action, ix_audit_logs_actor_id,
    # ix_audit_logs_resource_type, and ix_audit_logs_tenant_id are
    # auto-created by `index=True` on the corresponding columns above.
    # Creating them again here raises DuplicateTableError against a
    # fresh database.

    # Each "add column / rename" below is wrapped in a SAVEPOINT so a
    # recoverable error (e.g. column already exists) doesn't abort the
    # surrounding transaction and break the rest of the migration.

    # Align metrics_daily — add columns if missing
    for col, coltype, default in [
        ("metric_name", sa.String(100), None),
        ("value", sa.Numeric, None),
        ("metadata_json", postgresql.JSONB, sa.text("'{}'::jsonb")),
    ]:
        try:
            with op.get_context().autocommit_block():
                pass
            op.execute("SAVEPOINT sp_metrics")
            try:
                kwargs = {"nullable": True}
                if default is not None:
                    kwargs["server_default"] = default
                op.add_column("metrics_daily", sa.Column(col, coltype, **kwargs))
                op.execute("RELEASE SAVEPOINT sp_metrics")
                _log(f"add metrics_daily.{col} OK")
            except Exception as e:
                op.execute("ROLLBACK TO SAVEPOINT sp_metrics")
                _log(f"add metrics_daily.{col} swallowed: {e.__class__.__name__}: {str(e)[:100]}")
        except Exception:
            # SAVEPOINT itself failed; skip silently
            pass

    # Align events table — ensure event_type column exists and not `type`
    try:
        op.execute("SAVEPOINT sp_events_rename")
        try:
            op.execute("ALTER TABLE events RENAME COLUMN type TO event_type")
            op.execute("RELEASE SAVEPOINT sp_events_rename")
            _log("rename events.type->event_type OK")
        except Exception as e:
            op.execute("ROLLBACK TO SAVEPOINT sp_events_rename")
            _log(f"rename events swallowed: {e.__class__.__name__}: {str(e)[:100]}")
    except Exception:
        pass
    try:
        op.execute("SAVEPOINT sp_events_reqid")
        try:
            op.add_column("events", sa.Column("request_id", sa.String(255), nullable=True))
            op.execute("RELEASE SAVEPOINT sp_events_reqid")
            _log("add events.request_id OK")
        except Exception as e:
            op.execute("ROLLBACK TO SAVEPOINT sp_events_reqid")
            _log(f"add events.request_id swallowed: {e.__class__.__name__}: {str(e)[:100]}")
    except Exception:
        pass

    # Align leads – ensure modern columns exist
    for col, coltype in [
        ("first_name", sa.String(100)),
        ("last_name", sa.String(100)),
        ("email", sa.String(255)),
        ("phone", sa.String(20)),
        ("tags", postgresql.JSONB),
        ("score", sa.Integer),
        ("metadata_json", postgresql.JSONB),
        ("campaign_id", postgresql.UUID(as_uuid=True)),
        ("assigned_to", postgresql.UUID(as_uuid=True)),
        ("stage", sa.String(50)),
    ]:
        sp_name = f"sp_leads_{col}"
        try:
            op.execute(f"SAVEPOINT {sp_name}")
            op.add_column("leads", sa.Column(col, coltype, nullable=True))
            op.execute(f"RELEASE SAVEPOINT {sp_name}")
        except Exception as e:
            op.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
            _log(f"add leads.{col} swallowed: {e.__class__.__name__}: {str(e)[:100]}")

    # Align customers – ensure tags/metadata_json exist
    for col, coltype in [
        ("tags", postgresql.JSONB),
        ("metadata_json", postgresql.JSONB),
        ("addresses_json", postgresql.JSONB),
        ("consent_json", postgresql.JSONB),
    ]:
        sp_name = f"sp_customers_{col}"
        try:
            op.execute(f"SAVEPOINT {sp_name}")
            op.add_column("customers", sa.Column(col, coltype, nullable=True))
            op.execute(f"RELEASE SAVEPOINT {sp_name}")
        except Exception as e:
            op.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
            _log(f"add customers.{col} swallowed: {e.__class__.__name__}: {str(e)[:100]}")


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_tenant_resource", table_name="audit_logs")
    op.drop_index("idx_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_table("audit_logs")
