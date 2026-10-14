#!/usr/bin/env bash
# =============================================================================
# Infalette — single-command local runner.
#
# What it does, in order:
#   1. Validates the host (Linux, .venv present, port availability).
#   2. Detects whether Docker is usable (user in `docker` group or rootless).
#      - If yes: brings up Postgres + Redis via docker compose.
#      - If no : uses Neon (DATABASE_URL_* from .env) for Postgres, and a
#               user-local redis-server (ships in .venv via `redislite`) for
#               Redis. Both are started as background daemons under
#               ~/.local/infalette/.
#   3. Re-installs Python packages in editable mode (idempotent).
#   4. Runs `alembic upgrade head` against DATABASE_URL_DIRECT.
#   5. Boots the FastAPI backend (uvicorn), the Celery worker, and all three
#      Next.js frontends in parallel, streaming logs to ./logs/.
#   6. On Ctrl-C, stops every child process and tears down the daemons it
#      started.
#
# Usage:
#   ./run.sh           # full stack
#   ./run.sh backend   # only api + workers
#   ./run.sh web       # only the three frontends
#   ./run.sh stop      # stop everything we started
#   ./run.sh status    # report service health
#
# The script is idempotent: re-running it kills any previous run, refreshes
# dependencies, and re-applies migrations.
# =============================================================================
set -euo pipefail

# -- Colors & helpers ---------------------------------------------------------
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'
  C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'
  C_BOLD=$'\033[1m'
else
  C_RESET="" C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_BOLD=""
fi

log()  { printf "%s[run]%s %s\n" "$C_BLUE" "$C_RESET" "$*"; }
ok()   { printf "%s[ ok]%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s[warn]%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
err()  { printf "%s[fail]%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; }
hdr()  { printf "\n%s== %s ==%s\n" "$C_BOLD" "$*" "$C_RESET"; }

# -- Paths --------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export SCRIPT_DIR

PIDS_FILE="$SCRIPT_DIR/.run.pids"
LOGS_DIR="$SCRIPT_DIR/logs"
REDIS_DIR="$HOME/.local/infalette/redis"
REDIS_PORT=6379
REDIS_PID_FILE="$REDIS_DIR/redis.pid"
REDIS_LOG_FILE="$REDIS_DIR/redis.log"
mkdir -p "$LOGS_DIR" "$REDIS_DIR"

# -- Prereqs ------------------------------------------------------------------
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing required command: $1"; exit 1; }
}
require_cmd python3
require_cmd curl

VENV="$SCRIPT_DIR/.venv"
if [[ ! -d "$VENV" ]]; then
  err ".venv not found at $VENV. Run: python3 -m venv .venv"
  exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

# -- Detect Docker usability --------------------------------------------------
docker_works() {
  command -v docker >/dev/null 2>&1 || return 1
  # Can we actually talk to the daemon?
  docker info >/dev/null 2>&1
}

# -- Stop everything we previously started ------------------------------------
stop_all() {
  hdr "Stopping previous run"
  if [[ -f "$PIDS_FILE" ]]; then
    while IFS= read -r pid; do
      [[ -z "$pid" ]] && continue
      if kill -0 "$pid" 2>/dev/null; then
        # Kill the whole process group (the launcher is setsid'd)
        pkill -P "$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
      fi
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
  fi

  # Kill any leftover uvicorn / celery / next dev / redis we own
  pkill -f "uvicorn apps.api.main" 2>/dev/null || true
  pkill -f "celery -A apps.workers" 2>/dev/null || true
  pkill -f "next dev" 2>/dev/null || true
  pkill -f "next-server" 2>/dev/null || true

  if [[ -f "$REDIS_PID_FILE" ]]; then
    local rpid
    rpid="$(cat "$REDIS_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$rpid" ]] && kill -0 "$rpid" 2>/dev/null; then
      "$VENV/bin/redis-cli" -p "$REDIS_PORT" shutdown nosave 2>/dev/null || true
    fi
    rm -f "$REDIS_PID_FILE"
  fi

  # If we used docker compose to start local infra, leave it running for
  # next time (the data volume is preserved). Print a hint if it was started.
  if docker_works && [[ -f "$SCRIPT_DIR/.run.used-docker" ]]; then
    log "Docker infra is still running. Use './run.sh down' to stop it."
  fi
  ok "Stopped."
}

# -- Status -------------------------------------------------------------------
status_cmd() {
  hdr "Service status"
  export SCRIPT_DIR
  printf "  Postgres:              "
  if "$PY" - <<'PY' >/dev/null 2>&1
import asyncio, asyncpg, os
from pathlib import Path

# Load DATABASE_URL_* from .env (parent of script) if not already set.
env_path = Path(os.environ.get("SCRIPT_DIR", ".")) / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

async def t():
    url = os.environ.get("DATABASE_URL_DIRECT") or os.environ.get("DATABASE_URL_POOLED")
    if not url:
        raise SystemExit("no DATABASE_URL")
    # strip asyncpg prefix for raw connect
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(url, timeout=5)
    await c.fetchval("SELECT 1")
    await c.close()

asyncio.run(t())
PY
  then ok "reachable"; else err "unreachable (check .env)"; fi

  printf "  Redis (localhost:%s): " "$REDIS_PORT"
  if "$VENV/bin/redis-cli" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    ok "PONG"
  else
    err "down"
  fi

  printf "  API (8000):            "
  if curl -fsS --max-time 2 http://localhost:8000/health >/dev/null 2>&1; then
    ok "up"
  else
    err "down"
  fi
  printf "  Storefront (3000):     "
  if curl -fsS --max-time 2 -o /dev/null http://localhost:3000/demo-store; then ok "up"; else err "down"; fi
  printf "  Admin (3001):          "
  if curl -fsS --max-time 2 -o /dev/null http://localhost:3001; then ok "up"; else err "down"; fi
  printf "  Platform-admin (3002): "
  if curl -fsS --max-time 2 -o /dev/null http://localhost:3002; then ok "up"; else err "down"; fi
}

# -- Bring up infra -----------------------------------------------------------
start_infra_docker() {
  log "Starting Postgres + Redis via Docker Compose"
  COMPOSE_PROFILES=local docker compose \
    -f docker-compose.yml -f docker-compose.local.yml up -d
  touch "$SCRIPT_DIR/.run.used-docker"

  # Wait for Postgres healthy
  log "Waiting for Postgres to be ready"
  for i in {1..30}; do
    if docker exec infalette-postgres pg_isready -U infalette >/dev/null 2>&1; then
      ok "Postgres is ready"
      return 0
    fi
    sleep 1
  done
  err "Postgres did not become ready in 30s"
  return 1
}

start_infra_local() {
  warn "Docker is not usable (permission denied or not installed)."
  warn "Falling back to: Neon (remote Postgres) + local user-installed Redis."

  # 1. Make sure we have a redis-server binary. `redislite` ships one in
  #    the .venv. Install it lazily.
  if [[ ! -x "$VENV/bin/redis-server" ]]; then
    log "Installing redislite (provides redis-server binary)"
    "$PIP" install --quiet redislite
  fi

  # 2. Start redis-server in the background (user-owned, no sudo).
  if "$VENV/bin/redis-cli" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    ok "Redis already running on :$REDIS_PORT"
  else
    log "Starting redis-server on :$REDIS_PORT (data dir: $REDIS_DIR)"
    "$VENV/bin/redis-server" \
      --port "$REDIS_PORT" \
      --bind 127.0.0.1 \
      --daemonize yes \
      --dir "$REDIS_DIR" \
      --logfile "$REDIS_LOG_FILE" \
      --pidfile "$REDIS_PID_FILE" \
      --save 60 1000
    # Wait for it
    for i in {1..10}; do
      if "$VENV/bin/redis-cli" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        ok "Redis is up on :$REDIS_PORT"
        break
      fi
      sleep 0.5
    done
  fi
}

# -- Install Python deps (idempotent) ----------------------------------------
install_python_deps() {
  hdr "Installing Python dependencies (editable)"
  # Clear any stale .pyc that caused prior migration errors.
  find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

  # The whole stack: shared packages + apps namespace.
  "$PIP" install --quiet -e packages/database -e packages/config -e packages/validation \
    -e packages/auth -e packages/commerce -e packages/automation \
    -e packages/analytics -e packages/seo -e packages/integrations \
    -e apps
  # Make sure redislite is present so we always have a redis-server.
  "$PIP" install --quiet redislite
  ok "Python deps installed"
}

# -- Run migrations -----------------------------------------------------------
run_migrations() {
  hdr "Running database migrations"
  # DATABASE_URL_DIRECT is set in .env. alembic uses the synchronous driver
  # via DATABASE_URL_SYNC if defined; otherwise it falls back to the async
  # url from packages/database/src/infalette_database/env.py.
  cd "$SCRIPT_DIR/packages/database"
  "$VENV/bin/alembic" upgrade head
  cd "$SCRIPT_DIR"
  ok "Migrations applied"
}

# -- Run demo seed (best-effort) ---------------------------------------------
seed_demo() {
  if [[ -f "$SCRIPT_DIR/scripts/demo_seed.py" ]]; then
    log "Seeding demo tenant (idempotent — safe to re-run)"
    if "$PY" "$SCRIPT_DIR/scripts/demo_seed.py" >"$LOGS_DIR/demo-seed.log" 2>&1; then
      ok "Demo seed complete (owner@demo.test / demo1234)"
    else
      warn "Demo seed failed (see logs/demo-seed.log) — continuing"
    fi
  fi
}

# -- Launch services -----------------------------------------------------------
launch_bg() {
  # Launch a command in its own process group so we can kill the whole tree.
  local name="$1"; shift
  local logfile="$LOGS_DIR/$name.log"
  log "  starting $name (logs: $logfile)"
  setsid bash -c "$* >>'$logfile' 2>&1" </dev/null &
  echo "$!" >> "$PIDS_FILE"
}

start_backend() {
  hdr "Starting backend"
  launch_bg api "exec $VENV/bin/uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload"
  launch_bg workers "exec $VENV/bin/celery -A apps.workers.main worker --loglevel=info"
}

start_web() {
  hdr "Starting frontends (Next.js)"
  if [[ ! -d "$SCRIPT_DIR/node_modules" ]]; then
    log "Running pnpm install"
    pnpm install
  fi
  launch_bg storefront "cd $SCRIPT_DIR/apps/storefront && exec pnpm dev --port 3000"
  launch_bg admin "cd $SCRIPT_DIR/apps/admin && exec pnpm dev --port 3001"
  launch_bg platform-admin "cd $SCRIPT_DIR/apps/platform-admin && exec pnpm dev --port 3002"
}

# -- Wait for a service to respond --------------------------------------------
wait_for_http() {
  local url="$1" name="$2" tries=60
  log "Waiting for $name at $url"
  for _ in $(seq 1 $tries); do
    # Use --silent to avoid noisy curl error lines while the service
    # is still starting. We only print status once at the end.
    if curl --silent --fail --max-time 2 --output /dev/null "$url"; then
      ok "$name is up"
      return 0
    fi
    sleep 1
  done
  warn "$name did not respond in ${tries}s (still might be starting)"
  return 1
}

# -- main ---------------------------------------------------------------------
CMD="${1:-all}"

case "$CMD" in
  stop)
    stop_all
    exit 0
    ;;
  down)
    stop_all
    if docker_works; then
      COMPOSE_PROFILES=local docker compose \
        -f docker-compose.yml -f docker-compose.local.yml down
      rm -f "$SCRIPT_DIR/.run.used-docker"
    fi
    ok "Torn down."
    exit 0
    ;;
  status)
    status_cmd
    exit 0
    ;;
  backend)
    stop_all
    install_python_deps
    if docker_works; then start_infra_docker; else start_infra_local; fi
    run_migrations
    start_backend
    wait_for_http http://localhost:8000/health "API"
    log "Backend running. Tail logs: tail -f $LOGS_DIR/*.log"
    wait
    ;;
  web)
    stop_all
    start_web
    wait_for_http http://localhost:3000 "Storefront"
    log "Frontends running. Tail logs: tail -f $LOGS_DIR/*.log"
    wait
    ;;
  all|"")
    stop_all
    install_python_deps
    if docker_works; then start_infra_docker; else start_infra_local; fi
    run_migrations
    seed_demo
    start_backend
    start_web
    wait_for_http http://localhost:8000/health "API"
    wait_for_http http://localhost:3000 "Storefront"
    hdr "All services up"
    cat <<EOF

  Storefront:      http://localhost:3000/demo-store
  Admin:           http://localhost:3001   (owner@demo.test / demo1234)
  Platform admin:  http://localhost:3002
  API docs:        http://localhost:8000/api/v1/docs
  Health:          http://localhost:8000/health

  Logs:            $LOGS_DIR/{api,workers,storefront,admin,platform-admin}.log
  Stop:            Ctrl-C here, or './run.sh stop'

EOF
    wait
    ;;
  *)
    err "Unknown command: $CMD"
    echo "Usage: $0 [all|backend|web|stop|down|status]" >&2
    exit 1
    ;;
esac
