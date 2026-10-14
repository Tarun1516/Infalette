# Architecture Documentation

## Overview

Infalette is a multi-tenant, headless commerce SaaS built as a modular monolith.

## Components

- **Storefront**: Next.js public storefront
- **Admin**: Next.js admin dashboard
- **Platform Admin**: Next.js platform operations console
- **API**: FastAPI backend
- **Workers**: Celery background jobs

## Event Model

See [Event Model](event-model.md) for details.

## Tenant Isolation

See [Tenant Isolation](tenant-isolation.md) for details.
