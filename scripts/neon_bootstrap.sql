-- =============================================================================
-- Infalette — Neon / Postgres 18.6 bootstrap.
--
-- Idempotent. Safe to re-run. Apply this once per database, either:
--   * automatically by scripts/neon_bootstrap.sh
--   * manually: psql "$DATABASE_URL_DIRECT" -f scripts/neon_bootstrap.sql
--   * or as a Docker entrypoint (mounted by docker-compose.local.yml)
--
-- Notes:
--   * On Neon, `uuid-ossp` and `pgcrypto` are pre-installed; the
--     `CREATE EXTENSION IF NOT EXISTS` is a no-op there.
--   * `btree_gist` is NOT pre-installed on Neon; it must be enabled per
--     database once. Used by the RLS GUC pin helper and a couple of
--     exclusion constraints in 011/012.
--   * Neon already creates the role and database; we do NOT attempt to
--     CREATE ROLE / CREATE DATABASE here. The original init.sql did that
--     for the Docker-entrypoint path, which is irrelevant on Neon.
-- =============================================================================

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Application schema (kept for forward-compat; the ORM currently uses public)
CREATE SCHEMA IF NOT EXISTS infalette;

-- Grant schema privileges to the application role. The role name is supplied
-- by the caller via psql variable (default `neondb_owner` on Neon,
-- `infalette` on the local Docker container).
\set app_role `echo "${APP_ROLE:-infalette}"`

GRANT ALL ON SCHEMA infalette TO :"app_role";
GRANT ALL ON SCHEMA public TO :"app_role";
ALTER SCHEMA infalette OWNER TO :"app_role";
