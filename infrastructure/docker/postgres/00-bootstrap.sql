-- =============================================================================
-- Infalette — local Docker Postgres bootstrap (postgres:18-alpine).
--
-- Mounted by docker-compose.local.yml as /docker-entrypoint-initdb.d/00-bootstrap.sql
-- and run by the official postgres image the first time the data volume is
-- initialised.
--
-- This file is intentionally NOT used for Neon. For Neon, run
-- scripts/neon_bootstrap.sql via `psql "$DATABASE_URL_DIRECT" -f ...`
-- (or scripts/neon_bootstrap.sh).
--
-- Idempotent. Safe to re-run.
-- =============================================================================

-- Required extensions (no-op on Neon; needed here for parity).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Application schema.
CREATE SCHEMA IF NOT EXISTS infalette;
GRANT ALL ON SCHEMA infalette TO infalette;
GRANT ALL ON SCHEMA public TO infalette;
ALTER SCHEMA infalette OWNER TO infalette;
