# E2E smoke tests (Playwright)

Self-contained package — install and run from this directory:

```sh
pnpm install
npx playwright install chromium
pnpm test
```

## Environment variables

| Variable         | Default                 | Purpose                                    |
| ---------------- | ----------------------- | ------------------------------------------ |
| `STOREFRONT_URL` | `http://localhost:3000` | Base URL of the Next.js storefront app      |
| `CI`             | unset                   | When set, tests retry up to 2 times on fail |

## Seeding notes

- `/demo-store` and `/demo-store/products` require the demo tenant to be
  seeded. If those routes return >= 400, the affected test is **skipped** so
  the suite passes without seeded data.
- The cart page (`/cart`) works without seed data.
- To seed: run the API (`uvicorn apps.api.main:app`), then create a tenant
  with slug `demo-store` via `POST /api/v1/tenants/` and add a few products.
