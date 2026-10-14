#!/usr/bin/env bash
# =============================================================================
# scripts/neon_bootstrap.sh
#
# One-time setup for a Neon Postgres 18.6 project: create a branch from
# `main`, apply the bootstrap SQL (extensions + schema + grants).
#
# Prerequisites:
#   * neonctl installed and authenticated (`neonctl auth`)
#   * psql 15+ (Neon is Postgres 18)
#   * NEON_PROJECT_ID and DATABASE_URL_DIRECT exported in the environment
#
# Usage:
#   export NEON_PROJECT_ID=ep-foo-123456
#   export DATABASE_URL_DIRECT='postgresql://...neon.tech/neondb?sslmode=require'
#   export NEON_BRANCH=main           # optional, default main
#   ./scripts/neon_bootstrap.sh
#
# Re-running is safe: CREATE EXTENSION IF NOT EXISTS / CREATE SCHEMA IF NOT
# EXISTS make the SQL idempotent. The branch is only created when missing.
# =============================================================================
set -euo pipefail

: "${NEON_PROJECT_ID:?NEON_PROJECT_ID is required (e.g. ep-foo-123456)}"
: "${DATABASE_URL_DIRECT:?DATABASE_URL_DIRECT is required (psql-style DSN)}"
NEON_BRANCH="${NEON_BRANCH:-main}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="$SCRIPT_DIR/neon_bootstrap.sql"

if [[ ! -f "$SQL_FILE" ]]; then
  echo "error: bootstrap SQL not found at $SQL_FILE" >&2
  exit 1
fi

if ! command -v neonctl >/dev/null 2>&1; then
  echo "warning: neonctl not found; skipping branch creation. Install from https://neon.tech/docs/reference/cli-install" >&2
elif ! neonctl branches get "$NEON_BRANCH" --project-id "$NEON_PROJECT_ID" >/dev/null 2>&1; then
  echo "creating Neon branch '$NEON_BRANCH' on project $NEON_PROJECT_ID"
  neonctl branches create \
    --project-id "$NEON_PROJECT_ID" \
    --name "$NEON_BRANCH" \
    --parent main >/dev/null
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "error: psql is required to apply the bootstrap SQL" >&2
  exit 1
fi

echo "applying bootstrap SQL to $DATABASE_URL_DIRECT"
psql "$DATABASE_URL_DIRECT" \
  --set ON_ERROR_STOP=on \
  --set APP_ROLE="${APP_ROLE:-neondb_owner}" \
  -v ON_ERROR_STOP=1 \
  -f "$SQL_FILE"

echo "Neon bootstrap complete."
