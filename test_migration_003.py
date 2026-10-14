"""Run migration 003 step by step using asyncpg to find the abort cause."""
import asyncio
import os
import asyncpg

async def main():
    conn = await asyncpg.connect(
        os.environ.get("DATABASE_URL_DIRECT") or os.environ.get("DATABASE_URL_POOLED")
    )

    # Replay the create_table for audit_logs
    ddl = """
    CREATE TABLE audit_logs (
        id UUID DEFAULT uuid_generate_v4() NOT NULL,
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        actor_id UUID REFERENCES users(id),
        action VARCHAR(100) NOT NULL,
        resource_type VARCHAR(100) NOT NULL,
        resource_id UUID,
        payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ip_address VARCHAR(45),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        PRIMARY KEY (id)
    )
    """
    try:
        await conn.execute(ddl)
        print('OK: create audit_logs')
    except Exception as e:
        print('FAIL create audit_logs ->', e.__class__.__name__, str(e)[:300])

    # Now the explicit create_index calls
    for ix, col in [('idx_audit_logs_tenant_created', 'tenant_id, created_at'),
                    ('idx_audit_logs_tenant_resource', 'tenant_id, resource_type, resource_id')]:
        try:
            await conn.execute(f'CREATE INDEX "{ix}" ON audit_logs ({col})')
            print(f'OK: create {ix}')
        except Exception as e:
            print(f'FAIL: create {ix} ->', e.__class__.__name__, str(e)[:200])

    # Now the try/except blocks
    blocks = [
        ('add metrics_daily.metric_name', "ALTER TABLE metrics_daily ADD COLUMN metric_name VARCHAR(100)"),
        ('add metrics_daily.value', "ALTER TABLE metrics_daily ADD COLUMN value NUMERIC"),
        ('add metrics_daily.metadata_json', "ALTER TABLE metrics_daily ADD COLUMN metadata_json JSONB"),
    ]
    for name, sql in blocks:
        try:
            await conn.execute(sql)
            print('OK:', name)
        except Exception as e:
            print('FAIL:', name, '->', e.__class__.__name__, str(e)[:200])

    # events rename
    try:
        await conn.execute("ALTER TABLE events RENAME COLUMN type TO event_type")
        print('OK: rename events.type')
    except Exception as e:
        print('FAIL: rename ->', e.__class__.__name__, str(e)[:200])

    # events.request_id
    try:
        await conn.execute("ALTER TABLE events ADD COLUMN request_id VARCHAR(255)")
        print('OK: add events.request_id')
    except Exception as e:
        print('FAIL: add events.request_id ->', e.__class__.__name__, str(e)[:200])

    # leads columns
    for col, typ in [('first_name', 'VARCHAR(100)'), ('last_name', 'VARCHAR(100)'), ('email', 'VARCHAR(255)'),
                     ('phone', 'VARCHAR(20)'), ('tags', 'JSONB'), ('score', 'INTEGER'),
                     ('metadata_json', 'JSONB'), ('campaign_id', 'UUID'), ('assigned_to', 'UUID'),
                     ('stage', 'VARCHAR(50)')]:
        try:
            await conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {typ}")
            print(f'OK: add leads.{col}')
        except Exception as e:
            print(f'FAIL: add leads.{col} ->', e.__class__.__name__, str(e)[:200])

    # customers columns
    for col, typ in [('tags', 'JSONB'), ('metadata_json', 'JSONB'),
                     ('addresses_json', 'JSONB'), ('consent_json', 'JSONB')]:
        try:
            await conn.execute(f"ALTER TABLE customers ADD COLUMN {col} {typ}")
            print(f'OK: add customers.{col}')
        except Exception as e:
            print(f'FAIL: add customers.{col} ->', e.__class__.__name__, str(e)[:200])

    await conn.close()

asyncio.run(main())
