import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(
        'postgresql://neondb_owner:***REMOVED_DB_PASSWORD***@***REMOVED_NEON_HOST***.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
    )
    await conn.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    await conn.execute("UPDATE alembic_version SET version_num = '002_add_discount_codes'")
    await conn.close()
    print('Dropped audit_logs; reset to 002')
asyncio.run(main())
