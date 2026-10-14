# Infalette

A multi-tenant, headless commerce SaaS for influencers selling pregnancy, postpartum, baby and childcare products.

## Overview

Infalette is a white-label social commerce platform that allows influencers to launch branded commerce websites, sell products, and convert social conversations into trackable orders — all without requiring a new codebase for every influencer.

## Features

- **Multi-tenant architecture** — Each influencer gets their own tenant with custom domain, products, payment account, and theme
- **Three subscription plans** — Store, Store + Automation, Store + Automation + CRM (via feature flags)
- **Social commerce** — Instagram comment/DM automation and WhatsApp commerce flows
- **Full CRM** — Leads, conversations, unified timeline, and attribution
- **Analytics dashboard** — Sales, funnel reporting, and channel attribution
- **SEO optimized** — Server-side rendering, structured data, sitemaps

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo with pnpm |
| Storefront | Next.js, React, TypeScript |
| Admin Dashboard | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python (FastAPI), SQLAlchemy 2.0, Pydantic v2 |
| Database | PostgreSQL |
| Cache/Queue | Redis, Celery |
| Payments | Razorpay (India), Stripe Connect (International) |
| Social | Instagram Graph API, WhatsApp Cloud API |
| Observability | Sentry, OpenTelemetry |
| CI/CD | GitHub Actions |

## Getting Started

### Prerequisites

- Node.js 22+
- pnpm 9+
- Python 3.12+
- Docker and Docker Compose
- PostgreSQL 18.6 — Neon is the default; a local container is supported as a fallback
- Redis 7+ (or use Docker)

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd infalette

# Copy environment variables
cp .env.example .env
# Then fill in DATABASE_URL_POOLED and DATABASE_URL_DIRECT (see "Using Neon" below)
# — or skip and use the local Postgres overlay (see "Local Postgres fallback").

# Start infrastructure services
docker-compose up -d redis
# For local Postgres instead of Neon:
#   COMPOSE_PROFILES=local docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# Install dependencies
pnpm install

# Install Python packages
pip install -e packages/database -e packages/config -e packages/validation \
  -e packages/auth -e packages/commerce -e packages/automation \
  -e packages/analytics -e packages/seo -e packages/integrations \
  -e apps/api -e apps/workers

# Run database migrations (uses DATABASE_URL_DIRECT; on Neon, points at the
# direct endpoint to bypass the transaction-mode pooler)
cd packages/database && alembic upgrade head && cd ../..

# Start development servers
pnpm dev
```

### Using Neon (production / staging / CI)

The app reads two DSNs:

- `DATABASE_URL_POOLED` — transaction-mode pooled endpoint, used by the API
  and workers for all runtime queries.
- `DATABASE_URL_DIRECT` — direct endpoint, used ONLY by Alembic for migrations.

Get both from the Neon console (`Connection Details` → select "Pooled" vs
"Direct"), then:

```bash
export DATABASE_URL_POOLED='postgresql+asyncpg://neondb_owner:<pw>@ep-xxx-pooler.<region>.aws.neon.tech/neondb?sslmode=require'
export DATABASE_URL_DIRECT='postgresql+asyncpg://neondb_owner:<pw>@ep-xxx.<region>.aws.neon.tech/neondb?sslmode=require'
./scripts/neon_bootstrap.sh   # one-time: create branch + apply extensions/schema
```

`DATABASE_URL_POOLED` falls back to `DATABASE_URL` for tools that don't
distinguish, so the legacy single-DSN setup still works.

### Local Postgres fallback

If you don't have a Neon account, the local overlay brings up a
`postgres:18-alpine` container with extensions pre-installed:

```bash
COMPOSE_PROFILES=local docker compose -f docker-compose.yml \
  -f docker-compose.local.yml up
```

Set `DATABASE_URL_POOLED` and `DATABASE_URL_DIRECT` in `.env` to
`postgresql+asyncpg://infalette:infalette@localhost:5432/infalette` (the
`.env.example` defaults already point there).

### Development

```bash
# Run all services
pnpm dev

# Run only the API
cd apps/api && uvicorn apps.api.main:app --reload

# Run only the storefront
cd apps/storefront && pnpm dev

# Run tests
pnpm test

# Run linting
pnpm lint
```

## Documentation

- [Implementation Plan](implementation_plan.md)
- [Architecture Docs](docs/architecture/)
- [API Docs](docs/api/)
- [Runbooks](docs/runbooks/)
- [Compliance](docs/compliance/)

## License

Proprietary — All rights reserved.
# Infalette
# Infalette
