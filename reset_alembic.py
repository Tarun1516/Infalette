import asyncio, os, asyncpg
async def main():
    conn = await asyncpg.connect(
        os.environ.get("DATABASE_URL_DIRECT") or os.environ.get("DATABASE_URL_POOLED")
    )
    await conn.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    await conn.execute("UPDATE alembic_version SET version_num = '002_add_discount_codes'")
    await conn.close()
    print('Dropped audit_logs; reset to 002')
asyncio.run(main())
