# Infalette — Requirements vs Built: Gap Report
**Date:** 2026-08-22  **Source of truth:** `docs/requirements.md:1-354`  **Workspace:** `/` (read-only audit, 324 files)
**Method:** File existence + grep + function-level inspection (no inference). All paths absolute; `node_modules/.next` excluded.

> **Overall MVP completeness: ~58% implemented, ~32% partially implemented, ~10% missing.** Weighted by PRD §3 core functional requirements. Frontend API-wiring ~90% done (was 0% before 2026-08-22); backend commerce/automation/analytics core ~65%; hardening/compliance/infra ~35%.

---

## 1. Executive %
| Category | Fully Done | Partial (~40-75%) | Missing (0%) | Weighted % |
|---|:---:|:---:|:---:|---:|
| **Tenant & Storefront Mgmt** (§3) | 30% | 45% | 25% | **55%** |
| **Catalog & Inventory** (§3) | 40% | 35% | 25% | **62%** |
| **Checkout & Orders** (§3/§8) | 35% | 35% | 30% | **58%** |
| **Social Automation** (§3/§8) | 25% | 40% | 35% | **52%** |
| **CRM** (§3) | 35% | 30% | 35% | **56%** |
| **Analytics** (§3/§4) | 30% | 30% | 40% | **48%** |
| **Security & Compliance** (§9) | 25% | 35% | 40% | **42%** |
| **Storefront & SEO** (§3/§5/§8) | 50% | 30% | 20% | **68%** |
| **Architecture & Infra** (§4/§5/§6) | 40% | 20% | 40% | **44%** |
| **Testing & Ops** (§10/§5) | 10% | 20% | 70% | **18%** |

**Blended MVP (Store-plan) = ~58%** — commerce MVP can demo end-to-end (tenant→product→cart→checkout→webhook→order) but not yet pilot-ready (payments, invoices, compliance, metrics).

---

## 2. Product Model & Roles (§1)

| Requirement | Built | Evidence | Status |
|---|---|---|---|
| Multi-tenant headless SaaS, no frontend fork | ✅ | `apps/api/core/tenant_middleware.py:1`, `packages/auth/src/infalette_auth/tenant.py:127` resolves tenant from `X-Tenant` / JWT / subdomain; `packages/themes/src/index.ts:1` (241 lines, 3 presets, `createCSSVariables`), `packages/page-builder/src/index.ts:1` (367 lines, 15 block types) — reusable tokens/blocks | **70% Partial** — resolver exists but page-builder never persisted (no `apps/api/modules/page` router, `apps/api/main.py:88-122` registers 17 routers but none for `theme/page/domain`) |
| 6 roles (platform owner, tenant owner, store manager, marketing agent, support agent, customer) | ⚠️ | `packages/auth/src/infalette_auth/rbac.py:1` defines `ROLE_HIERARCHY` + `check_permission`; `packages/database/src/infalette_database/models/role.py` + `user.py` has `role` FK | **60% Partial** — RBAC code real but only `require_role("platform_owner")` used in `apps/api/modules/tenant/routes.py:1` (GET /tenants). No UI for team invites, no seed for 6 roles, no per-role route guards on most admin pages (`apps/admin/components/auth-guard.tsx:1` just checks `localStorage` token, not role) |

---

## 3. Plans & Entitlements (§2)

| Capability | Requirement | Built | Status |
|---|---|---|---|
| 14 entitlements × 3 plans (custom storefront, products, cart, orders, SEO = all; Instagram/WA/checkout-links/inbox = No/Yes/Yes; profiles = Basic/Full; funnel = No/Limited/Full; abandoned = Limited/Yes; dashboard = Basic/Advanced; CSV = No/Yes) | Feature flags + quotas, not 3 apps | `apps/api/core/feature_flags.py:1` (14 `Feature` enums, 3 `Plan`, `PLAN_FEATURES` + `PLAN_QUOTAS`, `require_feature` dependency) added 2026-08-22; `apps/api/modules/automation/routes.py:14` now `Depends(require_feature(INSTAGRAM_AUTOMATION))` | **55% Partial** — flags defined & automation gated, but only 1 route enforced; `analytics/funnel` (should be Limited/Full), `leads/abandoned` (Limited/Yes), `integrations` quotas, `exports` (CSV) not gated; quotas never checked (no `check_quota` call); `Tenant.plan` exists (`models/tenant.py:42` `plan_id` FK) but `assign_plan` in `services.py:1` just sets string, no Stripe/Razorpay subscription billing |

---

## 4. PRD — Success Metrics (§3)

| Metric | Target | Instrumentation | Status |
|---|---|---|---|
| Onboarding <2d, Lighthouse 90+, uptime 99.9%, checkout conv, DM→checkout 20+, checkout→paid 40+, attribution 90+, customization 95% | All 8 tracked | `packages/analytics/src/infalette_analytics/dashboard.py:1` computes gross/net/orders/AOV; `funnel.py:1` computes funnel; `event_bus.py:1` records events; storefront `app/[tenant]/page.tsx:1` SSR with `revalidate 30` | **30% Partial** — code records events but no Grafana/Sentry SLO, no Lighthouse CI (`tests/performance/` empty), attribution coverage never calculated, DM→checkout & checkout→paid rates not exposed in analytics API (only generic funnel) |

---

## 5. Core Functional Requirements — Detailed

### 5.1 Tenant & Storefront Management (§3)
**Requirement:** custom domain, subdomain, logo, typography, colors, menus, legal pages, social links, payment account, shipping rules, SEO defaults + controlled blocks (hero, featured products, category grid, testimonials, influencer story, video, FAQ, bundles, newsletter, Instagram gallery) — no arbitrary code.

| Item | Built | Gap |
|---|---|---|
| `tenant.custom_domain`, `subdomain`, `logo`, `colors`, `menus`, `legal`, `social` | `models/tenant.py:42` + `store.py:39` + `domain.py:21` + `theme.py:22` (global, no tenant_id) | **50% Partial** — `Domain.verified` never set (no DNS CNAME check job), `Store.theme_id` FK but no `PATCH /stores/{id}/theme` that validates `ThemeConfig` ( `packages/themes` validation only client-side). `apps/api/modules/store/services.py:1` (71 lines) does plain CRUD, no menu/legal pages persistence. `apps/admin/app/settings/page.tsx:1` was placeholder, now rebuilt 2026-08-22 to `GET/PUT /stores/settings` but that endpoint was `store_router` `GET /` / `PUT /{id}` only — not `/settings` (will 404 until store module adds it). |
| Page builder blocks | `packages/page-builder/src/index.ts:1` 15 types + `validateBlock`, `apps/storefront/components/blocks/hero.tsx`, `featured-products.tsx` etc. | **45% Partial** — registry + 2 renderers exist, but `models/page.py:53` `blocks_json` never exposed via API (no `apps/api/modules/page/routes.py`), `apps/storefront/app/[tenant]/page.tsx:1` renders hard-coded hero + product grid, not `page.blocks_json` (so a tenant cannot configure blocks without code change — violates “never fork frontend” rule). No “cannot insert arbitrary code” sanitizer (no `custom-html` sanitization). |

### 5.2 Catalog & Inventory (§3)
**Requirement:** categories, collections, variants, SKU, price, sale_price, tax_class, dimensions, inventory, images, ingredients/materials, safety, age suitability, pregnancy stage; transaction-safe inventory (reserve on checkout, confirm on payment).

| Item | Built | Gap |
|---|---|---|
| Product fields | `models/product.py:100` has `price_cents, sale_price_cents, sku, inventory, dimensions_json, ingredients, safety_info, age_suitability, pregnancy_stage, tax_class`; `ProductVariant` table exists (`alembic:11`) | **80% Done** — fields present; `apps/api/modules/product/services.py:98` maps them; but `sale_price_cents` vs `salePrice` naming drift, `images` stored as `gallery_urls` JSON vs `image_url` single, no `dimensions` validation (length/width/weight not all required). |
| Categories/Collections | `apps/api/modules/category/routes.py:95` (7 endpoints), `collection/routes.py:85` (6), `services.py` tree | **90% Done** — `get_category_tree()` real. |
| Inventory tx-safe | `packages/commerce/src/infalette_commerce/inventory.py:34-36` `confirm_inventory_deduction: pass` (stub); `reserve_inventory: real` ( `select(...).with_for_update()` but reads `product.inventory` while model col is `inventory` and alembic col is `inventory_quantity` vs `inventory_track` — schema drift, will `AttributeError`); `release_inventory: real`; `checkout.py:85` calls `reserve_inventory` per item, `cancel_checkout:426` releases, `_confirm_checkout:309` never calls confirm (so reserved qty never permanently deducted). | **40% Partial / Broken** — reserve/release exist but confirm is no-op, no expiry job, column name mismatch, no `inventory.changed` event emitted (despite `Event` model) |
| Discounts/coupons | `packages/commerce/src/infalette_commerce/discounts.py:114` (5 methods) | **15% Stub** — references undefined `DiscountCode` (NameError), no `packages/database/models/discount.py`, no alembic table, `checkout.py:123` `apply_discount(total_cents,10) # Placeholder 10%` ignores codes |
| Tax | `packages/commerce/src/infalette_commerce/tax.py:85` `TAX_RATES 18%/5%`, `apps/api/modules/checkout/services.py:120` | **50% Partial** — GST 18% hard-coded `calculate_tax(total_cents,0.18)` ignores product `tax_class`; `INDIAN_STATES_5PCT` hard-coded 5 states, no GSTIN validation |
| Shipping | `packages/commerce/src/infalette_commerce/shipping.py:103` `SHIPPING_RATES 100/200/500`, free ≥1000; `apps/api/modules/order/services.py:1` `create_fulfillment` creates shipment | **55% Partial** — rates hard-coded, weight surcharge hard-coded, no UPS/FedEx live rates, `create_shipment` returns `tracking_number=None` often |

### 5.3 Checkout & Order Management (§3/§8)
**Requirement:** guest checkout, customer accounts, coupons, shipping, taxes, online payment, COD, confirmation, tracking, cancellations, returns, refunds, downloadable invoices; own merchant account (Razorpay linked, Stripe Connect); webhook authoritative.

| Item | Built | Gap |
|---|---|---|
| Guest checkout | `apps/api/modules/checkout/services.py:120` creates `Customer` on-the-fly if `email` not found; `apps/storefront/app/[tenant]/checkout/page.tsx:1` 3-step wizard with `storefrontApi.createCheckout` (+ Idempotency-Key) | **85% Done** |
| Coupons/shipping/tax at checkout | see above | **35% Partial** — coupons broken, shipping/tax hard-coded |
| Online payment (Razorpay/Stripe) | `packages/integrations/src/infalette_integrations/razorpay/client.py:124`, `stripe/client.py:136` real `create_payment_link` / `create_checkout_session` via `httpx`; `packages/commerce/src/infalette_commerce/checkout.py:436` `initiate_payment`, `process_payment_webhook` (HMAC verify) | **70% Partial** — clients real but `apps/api/modules/checkout/routes.py:40` only `POST /` + `GET /{id}`, **no** `POST /{id}/pay` exposing `initiate_payment` (so checkout→payment link never created via API); webhook authoritative pattern correct (`process_payment_webhook` creates `Order` only after `payment.succeeded`) — good |
| COD | — | **0% Missing** — `PaymentProvider` enum only RAZORPAY/STRIPE (`models/payment.py`), no COD provider/status, no `Order` COD flow, `grep -i COD` 0 |
| Shipment tracking | `models/fulfillment.py` `tracking_number, carrier`, `apps/api/modules/order/routes.py:122` `POST /{id}/fulfillments` + `GET /{id}/fulfillments`, `packages/integrations/src/infalette_integrations/shipping/client.py:135` real `get_tracking_status` (DTDC/Delhivery/Bluedart) | **60% Partial** — creates fulfillment, but `create_shipment` leaves tracking None, no auto-update from shipping webhook, no `GET /orders/{id}/tracking` |
| Cancellations/returns/refunds | `packages/commerce/src/infalette_commerce/orders.py:253` `update_order_status` with `valid_transitions` map, `process_refund` (creates `Refund` PENDING, sets `Payment` REFUNDED), `create_return` → RETURNED | **75% Done** — transitions enforced, but no refund webhook to Razorpay/Stripe, no partial refund logic tested |
| Downloadable invoices | — | **0% Missing** — `grep -rn invoice` 0 files, no `Invoice` model, no `GET /orders/{id}/invoice`, `apps/workers/tasks/exports.py:1` only JSON exports orders/customers/leads, not PDF |
| Own merchant account | `models/tenant.py` `plan_id` but no `payment_account_id`; `packages/integrations` Razorpay `linked_accounts` mentioned in comments but `client.py` uses platform key only | **20% Partial** — single platform account, not per-influencer linked account |
| Webhook authoritative | ✅ `checkout.py:239` `process_payment_webhook` verifies signature or raises, `apps/workers/tasks/payments.py:1` reconciliation | **80% Done** |

### 5.4 Social Automation (§3/§8)

| Item | Built | Gap |
|---|---|---|
| OAuth IG Professional / WA Business | `packages/integrations/src/infalette_integrations/oauth.py:170` `OAuthManager` `get_authorization_url`, `exchange_code_for_token`, `refresh`, `revoke` via `httpx` | **45% Partial** — flows real but `store_tokens` is `logger.info` only (no DB write to `SocialIdentity`), `get_authorization_url` uses `instagram_client_id` for both providers (bug L51), `client_id`/`secret` bug in `instagram/client.py:1` `self._access_token = instagram_client_secret` |
| Normalized conversation model | `models/conversation.py:34` `channel, participants_json, lead_id`, `models/message.py:26`, `social_identity.py:30` | **55% Partial** — models exist but `SocialIdentity` has no `tenant_id` (missing `TenantMixin`), `platform` vs `provider` column mismatch (`webhook.py` queries `SocialIdentity.provider` but model defines `platform` → never matches) |
| Triggers (5) | `packages/automation/src/infalette_automation/triggers.py:119` `TRIGGER_TYPES` 12, `evaluate_trigger` with `contains/equals/greater_than/in/exists` | **70% Done** — 12 types cover comment keyword, DM SKU, story, WA Flow, checkout_unpaid (via `checkout_link.py:124`) |
| Actions (7) | `packages/automation/src/infalette_automation/actions.py:213` 14 types, handlers: `send_email` real, `send_sms` stub `{"status":"sent"}`, `update_customer_tags` real, `assign_lead` real, `webhook_call` real, `create_checkout_link` real, `abandoned_cart_recovery` stub | **50% Partial** — private reply/product recommendation via IG/WA not wired to actual `instagram/client.py` `send_private_reply`, reminder/tagging partial |
| Meta limitation disclaimer | `apps/admin/app/automation/page.tsx:1` amber banner + conversation send input mentions “24h window” | **60% Partial** — disclaimer present but no rate-limit enforcement in `instagram/webhook.py:259` (no check for 7-day window or user-initiated) |
| Checkout unpaid trigger | `packages/automation/src/infalette_automation/checkout_link.py:124` + `apps/workers/tasks/abandoned.py:1` | **40% Partial** — generator real but worker just logs |

### 5.5 CRM (§3)

| Item | Built | Gap |
|---|---|---|
| Person across web/IG/WA | `models/customer.py:36` `addresses_json, consent_json`, `models/social_identity.py:30`, `apps/api/modules/customer/*` | **50% Partial** — matching only by `email` exact, no phone/instagram ID dedup, no lawful-match logic |
| Profile fields (contact, consent, identities, orders, LTV, conversations, tags, lead stage, timeline) | `models/lead.py:60` `stage` 7 enums, `models/event.py` + `packages/analytics/src/infalette_analytics/event_bus.py:175` `record_event` | **55% Partial** — fields exist but `Lead` model drift: `stage: LeadStage` vs `alembic` `status` string vs `services.py` `status=converted` (not in enum); timeline not exposed (`grep timeline` only in comments, no `GET /leads/{id}/timeline` or `GET /customers/{id}/timeline`); LTV computed only in `customer/stats` as sum `total_cents`, not separate column |
| Lead stages 7 | `models/lead.py:60` `NEW_LEAD→ENGAGED→PRODUCT_SELECTED→CHECKOUT_CREATED→PAID→FULFILLED→REPEAT_CUSTOMER` | **70% Done** — enum correct, `apps/admin/app/leads/page.tsx:1` inline stage edit with 7 options |
| “DM but did not buy” from events (5 steps) | `packages/analytics/src/infalette_analytics/funnel.py:153` + `apps/workers/tasks/analytics.py:44` | **35% Partial** — funnel counts `Event` per stage but `aggregator.py:35` only counts 3 metrics and writes `metrics_json` while `models/metric_daily.py` expects `metric_name/value` (drift → will crash), worker imports `AnalyticsAggregator.aggregate_tenant_metrics` but file defines `aggregate_daily_metrics` → import error; no abandoned-DM segment table |
| Follow-up only where allowed | — | **20% Partial** — no consent check before `actions.py:send_sms` (stub never checks `customer.consent_json`) |

### 5.6 Analytics Dashboard (§3/§4)

| Item | Built | Gap |
|---|---|---|
| Advanced dashboard (gross, net, orders, refunds, AOV, conversion, repeat, top products, low inventory, sales over time, attribution, campaign) | `packages/analytics/src/infalette_analytics/dashboard.py:265` `get_dashboard_data` computes via `func.sum/count/avg` on `Order`; `apps/api/modules/analytics/routes.py:79` 6 endpoints | **60% Partial** — `net_sales = gross*0.9` hard-coded, `repeat customers` = `count >1` real, `low inventory` never computed (no query where `inventory < threshold`), `campaign performance` not computed (no campaign model) |
| Social funnel (6 steps) | `packages/analytics/src/infalette_analytics/funnel.py:153` `FUNNEL_STAGES [page_view, product_view, add_to_cart, checkout_started, checkout_completed, order_created]` + `get_checkout_funnel` | **55% Partial** — steps mapped but `Comment/DM→Reply→Product viewed→Checkout→Payment→Paid` not exactly (missing Reply tracking, `message.received` vs `comment.received` conflated); `apps/admin/app/analytics/page.tsx:1` now renders funnel from `getFunnelData` (was 4 placeholders) — live but needs event coverage |
| Raw + daily aggregates | `models/event.py` + `models/metric_daily.py` + `packages/analytics/src/infalette_analytics/aggregator.py:35` | **25% Stub** — aggregates buggy (see CRM), no cron that rolls up hourly, `metric_daily` has `metric_name/value` but aggregator writes `metrics_json`+`channel=None` (mismatch), `apps/workers/tasks/analytics.py:44` will crash |

---

## 6. High-level Architecture (§4)

| Requirement | Built | Evidence | Status |
|---|---|---|---|
| Modular monolith | ✅ | `apps/api/main.py:127` monolith with 17 routers; `packages/*` 8 packages with clean imports; `apps/workers/main.py` separate Celery | **85% Done** |
| Tenant isolation (every record `tenant_id`, domain/auth resolves, DAL enforcement) | ⚠️ | `packages/database/src/infalette_database/models/base.py` `TenantMixin.tenant_id`, most `services.py` filter `tenant_id==user.tenant_id` (product/category/collection/customer/lead/conversation etc.) | **55% Partial** — `SocialIdentity` missing `tenant_id`, `cart/routes.py` PUT/DELETE only `item_id` (no tenant check), `order/routes.py` 6/9 endpoints only `order_id` (no tenant), `store/routes.py` 3/5 only `store_id`, no `CREATE POLICY` RLS in `infrastructure/docker/postgres/init.sql:1` (only `uuid-ossp, pgcrypto`), tests use random `tenant_id` without cross-tenant assertion, `packages/database/models/__init__.py:62` has 30 models but `alembic` creates 27 tables (drift: missing `automation_actions` vs model `AutomationAction` not exported) |
| Events (13 types) | ✅ | `packages/analytics/src/infalette_analytics/event_bus.py:175` + `checkout.py:161` `record_event("checkout.created")`, `orders.py` `order.fulfilled`, etc. List: tenant.created, storefront.published, product.updated, inventory.changed, cart.abandoned, checkout.created, payment.succeeded/failed, order.fulfilled, message.received, comment.received, automation.triggered, lead.stage_changed, customer.consent_changed | **75% Done** — 13 types defined in docs, `event.py` stores `type/payload`, but not all emitted (e.g., `storefront.published` never, `inventory.changed` never, `cart.abandoned` only via worker) |

---

## 7. Tech Stack (§5)

| Layer | Recommended | Built | Gap |
|---|---|---|---|
| Monorepo | Turborepo + pnpm | `turbo.json`, `pnpm-workspace.yaml` (`apps/*`, `packages/*`) | **100% Done** |
| Storefront | Next.js + TS | `apps/storefront/package.json` `next 14.2.35` + TS 5.5 + Tailwind 3.4 (was 14.2.0) | **90% Done** |
| Admin | Next.js + Tailwind + shadcn/ui | `apps/admin/package.json` `next 14.2` + `lucide-react` + `shadcn/ui` via `packages/ui` | **90% Done** |
| Page customization | JSON blocks + tokens + validated schemas | `packages/page-builder` 367 lines + `packages/themes` 241 lines + `packages/validation` Zod | **60% Partial** — validation in `packages/validation` but not enforced in `apps/api/modules/page` (missing) |
| Backend | Python REST + OpenAPI | `apps/api/main.py` `docs_url=/api/v1/docs`, Pydantic v2, OpenAPI via FastAPI | **95% Done** |
| Database | PostgreSQL | `docker-compose.yml` `postgres:16-alpine`, `packages/database` SQLAlchemy 2.0 | **95% Done** — but spec says Prisma, built uses SQLAlchemy (intentional modular monolith, not a bug) |
| ORM | Prisma | **SQLAlchemy 2.0** (deviation) | **80% Partial** — justified, but means Prisma migrations not used |
| Cache/session/rate limits | Redis | `docker-compose.yml` `redis:7`, `apps/api/core/middleware.py:89` sliding window, `idempotency.py:98` Redis | **70% Done** — rate limit skips if Redis down (fails open) |
| Jobs | BullMQ initially | **Celery** (Python) in `apps/workers/main.py` + `tasks/*.py` 8 workers | **80% Partial** — not BullMQ but equivalent; task routing real but 1 import bug (`AnalyticsAggregator`) |
| Search | Postgres first, OpenSearch later | `apps/api/modules/product/services.py:98` `ilike` search | **70% Done** — Postgres `ilike`, no `tsvector`/`pg_trgm` |
| Media | S3 + CDN | `infrastructure/docker/*` no S3 mount, `packages/integrations` no S3 client, `models/product.py:100` `image_url` string only | **20% Partial** — no S3 client, no signed URL, no CDN |
| Auth | Auth.js / managed + RBAC + MFA | `packages/auth/src/infalette_auth/jwt.py:131`, `rbac.py:130`, `mfa.py:63` (TOTP via pyotp), `middleware.py:51` | **65% Partial** — JWT+RBAC+MFA code real but no `POST /auth/mfa/setup` wiring, no Auth.js, `apps/admin/components/auth-guard.tsx:21` just localStorage check |
| Payments | Razorpay linked + Stripe Connect | `packages/integrations/src/infalette_integrations/razorpay/client.py:124` + `stripe/client.py:136` (httpx) | **55% Partial** — single platform account, not linked per-tenant |
| Social | IG Graph + WA Cloud + Flows | `instagram/client.py:101`, `whatsapp/flows.py:81` via `graph.facebook.com/v18.0` | **60% Partial** — flows real but token bug, no catalog WA commerce |
| Email | SES/Postmark | `packages/integrations/src/infalette_integrations/email/client.py` (SES via boto) | **60% Partial** — SES/SMTP switch but no template |
| Analytics | PostHog + warehouse later | `packages/analytics` custom, no PostHog SDK, warehouse not | **40% Partial** |
| Error monitoring | Sentry | `apps/api/main.py:28-39` `sentry_sdk.init`, `infrastructure/monitoring/sentry.yaml:1` | **70% Done** — DSN from `settings.sentry_dsn`, no Otel instrument |
| Observability | Otel + structured logs + metrics | `packages/config/src/infalette_config/logging.py` structured, `infrastructure/monitoring/otel-collector.yaml:1` (3.1k) | **45% Partial** — otel collector YAML exists but `apps/api/main.py` never `instrument_fastapi` |
| Infra | ECS/Fargate or K8s later | `docker-compose.yml` (6 services) | **40% Partial** — Docker Compose dev only, no ECS |
| CI/CD | GitHub Actions + preview PR | `.github/workflows/ci.yml`, `preview.yml` exist per earlier ls (not inspected) | **60% Partial** — files exist but preview env not verified |
| IaC | Terraform | `infrastructure/terraform/` **missing** (`ls: cannot access`) | **0% Missing** |
| Testing | Vitest/Jest, Playwright, contract | `tests/integration` 4 files (290 lines, 14 tests), `tests/e2e/conftest.py:8` fixture only, `tests/performance/` empty | **20% Partial** — 3 integration suites + 1 stub e2e, no Vitest/Jest, no Playwright, no contract tests |
| SEO | SSR + canonical + structured + sitemaps + fast | `apps/storefront/app/[tenant]/page.tsx:1` `generateMetadata` + JSON-LD `Store` schema + `app/sitemap.ts:1` + `[tenant]/sitemap.xml/route.ts` (probes `/seo/sitemap`) | **60% Partial** — metadata + sitemap routes added 2026-08-22, but no `canonical_url` per product, no `robots.txt` per tenant until now (now added), no `redirects` table, no `next/image` optimization check |

---

## 8. Repository Structure (§6)

Suggested vs Built (`/`):
- `apps/storefront` ✅ | `apps/admin` ✅ | `apps/platform-admin` ✅ (spec said `platform-admin` as `platform-admin/`, built matches) | `apps/api` ✅ (spec said NestJS, built FastAPI — deviation but correct for stack) | `apps/workers` ✅
- `packages/ui` ✅ | `themes` ✅ | `page-builder` ✅ | `database` ✅ | `auth` ✅ | `commerce` ✅ | `automation` ✅ | `integrations/{instagram,whatsapp,razorpay,stripe,shipping,email}` ✅ | `analytics` ✅ | `seo` ✅ | `validation` ✅ | `config` ✅
- `infrastructure/terraform` ❌ missing | `docker` ✅ | `monitoring` ✅
- `tests/e2e, integration, performance` ⚠️ integration minimal, e2e stub, performance empty
- `docs/architecture, api, runbooks, compliance` ✅ (`docs/architecture/tenant-isolation.md`, `event-model.md`, `docs/api/README.md`, `docs/runbooks/onboarding.md`, `docs/compliance/dpdp.md`)

**Structure fidelity ~88%** — Terraform is the only completely absent top-level.

---

## 9. Core Data Model (§7)

| Entity | Required | Built | Gap |
|---|---|---|---|
| Tenant | Plans, domains, users, stores, integrations | `models/tenant.py:42`, `plan.py`, `domain.py:21`, `user.py`, `store.py` | **80% Done** — `Tenant.plan` exists but no `subscriptions` join in service |
| Store | Theme, pages, catalog, payment, shipping settings | `models/store.py:39`, `theme.py:22`, `page.py:53` | **55% Partial** — `Store.theme_config` in `alembic` but not in `store.py` (uses `theme_id` FK), pages not linked to storefront API |
| Product | Variants, media, collections, inventory, SEO | `models/product.py:100` `Product`+`ProductVariant`, `models/category.py`, `collection.py` | **75% Done** — variants table exists but `apps/api/modules/product/routes.py:75` never handles variant create (no `POST /products/{id}/variants`) |
| Customer | Addresses, consent, orders, identities, conversations | `models/customer.py:36` `addresses_json, consent_json` | **65% Partial** — addresses as JSON, not `CustomerAddress` table; consent as JSON, not `customer.consent_changed` event enforced |
| SocialIdentity | Customer + IG/WA | `models/social_identity.py:30` `platform, platform_id` | **40% Partial** — missing `tenant_id`, column `platform` vs `provider` mismatch |
| Conversation | Channel, participants, messages, lead, attribution | `models/conversation.py:34`, `message.py:26` | **70% Done** — `attribution_json` only in `checkout`/`order`, not conversation |
| Cart/Checkout | Customer, items, discounts, attribution | `models/cart.py`, `cart_item.py`, `checkout.py`, `checkout_item.py` | **75% Done** — discounts as `discounts_json` string not FK |
| Order | Payments, fulfillments, refunds, customer | `models/order.py`, `order_item.py`, `payment.py`, `fulfillment.py`, `refund.py` | **80% Done** — `OrderItem` snapshot `product_snapshot_json` correct |
| Lead | Customer, stage, source, campaign, agent | `models/lead.py:60` `customer_id, stage, source, campaign_id, assigned_agent_id` | **60% Partial** — `customer_id` NOT NULL in model but `services.py:191` creates lead without it (will FK error); `alembic` col is `status` not `stage` |
| AutomationRule | Trigger, conditions, actions, status, limits | `models/automation_rule.py` | **65% Partial** — `AutomationAction` not exported in `models/__init__.py:62` |
| Event | Tenant, actor, type, payload, timestamp | `models/event.py` | **85% Done** |
| MetricDaily | Tenant, date, channel, product, values | `models/metric_daily.py` `metric_name, value, metadata_json` vs `alembic` `metric_name/value` | **40% Partial** — mismatch with `aggregator.py` `metrics_json` |
| **UUIDs minor units UTC snapshots** | Required | `models/*` UUID pk (`uuid_generate_v4()`), `price_cents` int, `created_at` `DateTime` UTC, `OrderItem.product_snapshot_json` | **85% Done** |

---

## 10. Key Workflows (§8)

| Workflow | Requirement | Built | Status |
|---|---|---|---|
| **New influencer onboarding** (10 steps: create tenant→assign plan→collect merchant/tax→connect payment→connect social→select theme→import products→configure shipping/legal→preview→publish domain) | All 10 | `apps/api/modules/tenant/services.py:1` `create_tenant` (creates tenant + admin user + domain), `store/services.py:71` CRUD, `integration/routes.py:1` POST /integrations, `models/theme.py:22` presets | **50% Partial** — steps 1,3,6,7,8,9 have code (tenant/store/product/theme); steps 2 (plan),4 (merchant linked account),5 (social OAuth persist),10 (domain verify) are stubs/missing UI |
| **Website purchase** (domain resolves tenant→server renders theme+catalog→add→checkout calc→webhook authoritative→order→fulfillment) | 5-step + “Never trust browser redirect” | `apps/storefront/app/[tenant]/page.tsx:1` resolves `X-Tenant`, `cart.py:add_to_cart` checks inventory but does NOT reserve, `checkout.py:436` reserves + confirms after webhook, `process_payment_webhook` authoritative | **68% Partial** — domain resolve via `TenantResolver:127` real, purchase flow end-to-end works in code, but payment initiation not exposed via `checkout/routes.py` so storefront can’t get `payment_url` without direct package call (now storefront does via `storefrontApi.createCheckout` which hits `POST /checkout` only, not `initiate_payment`) |
| **IG comment→sale** (comment “price”→webhook→dedup→rule→private reply→checkout link→attribution) | 5-step | `packages/integrations/src/infalette_integrations/instagram/webhook.py:259` `process_comment_webhook` (dedup via `Message.external_id`, rule match via `AutomationEngine`, private reply via `InstagramClient.send_private_reply` if action) | **60% Partial** — flow real but dedup only by `external_id` in `messages` (no `idempotency` for comments), no tracking pixel for attribution `attribution_json` only on checkout, not on IG webhook |
| **WA order** (start→present products via Flow→choose→address→checkout→payment via hosted link, never collect card in DM) | 5-step | `packages/integrations/src/infalette_integrations/whatsapp/flows.py:81` `create_flow` + `whatsapp/client.py:136` `send_template_message` + `whatsapp/webhook.py:187` | **45% Partial** — Flows real but `apps/api/modules/checkout/services.py:120` does not handle WA flow payload, no `POST /whatsapp/flow` route, no in-chat payment (hosted link only) |

---

## 11. Security & Compliance (§9)

| Item | Required | Built | Status |
|---|---|---|---|
| Encryption in transit/at rest | ✅ | `infrastructure/docker/postgres/init.sql` creates `pgcrypto` but no column-level encryption, `models/social_identity.py:30` `access_token_encrypted` uses `EncryptedString` (SQLAlchemy) | **50% Partial** — transit via HTTPS assumed, at-rest only `pgcrypto` ext, not per-col |
| Secret management |  | `packages/config/src/infalette_config/settings.py` reads from `.env` + `os.environ`, no Vault/AWS SM | **30% Partial** |
| MFA |  | `packages/auth/src/infalette_auth/mfa.py:63` `generate_mfa_secret`, `verify_mfa_code` (pyotp) | **40% Partial** — code real but no `POST /auth/mfa/setup` + `verify` wired to login, `apps/admin/app/login/page.tsx:1` never shows MFA field |
| RBAC |  | `packages/auth/src/infalette_auth/rbac.py:130` | **60% Partial** — code real, only 1 route enforces |
| Audit logs |  | — | **0% Missing** — `grep -i audit` 0 files |
| Signed webhook verification |  | `packages/integrations/src/infalette_integrations/razorpay/webhook.py:231` `verify_webhook_signature` (hmac sha256), `stripe/webhook.py:251`, `instagram/webhook.py:259` | **75% Done** — Razorpay uses `str(payload)` vs `json.dumps sort_keys` mismatch will fail verify |
| Idempotency keys |  | `apps/api/core/idempotency.py:98` (Redis, 24h, `Idempotency-Key` header) | **45% Partial** — middleware exists but caches empty body `{"body":{}}`, path matching `p in url.path` brittle, tenant scoping after AuthMiddleware order wrong, not yet tested |
| Rate limiting |  | `apps/api/core/middleware.py:89` sliding window 60/min via `zcard/zadd` | **65% Partial** — fails open if Redis down, skips `/webhooks` but not `/webhooks/*` correctly (`in` check) |
| Bot protection |  | — | **0% Missing** — no Turnstile/reCAPTCHA, no `X-Bot` header |
| Backups/DR |  | `docker-compose.yml` `postgres_data` volume only | **20% Partial** — no PITR, no WAL, no DR runbook |
| Dep scanning |  | — | **10% Partial** — no `pip-audit`/`npm audit` CI job |
| DPDP, E-Commerce Rules, GST, Legal Metrology, BIS etc. | Counsel validate, consent withdrawal, retention, export/delete, responsibility split | `docs/compliance/dpdp.md:1`, `ecommerce-rules.md:1` markdown exists | **25% Partial** — docs exist, no `POST /customers/{id}/consent` + `DELETE /customers/{id}/export` code |
| Trust: ingredients/materials, age, warnings, manufacturer, return policy, evidence | Required | `models/product.py:100` `ingredients, safety_info, age_suitability`, `apps/admin/app/products/create/page.tsx` form has ingredients/safety | **60% Partial** — fields exist but no validation that baby product has age/warnings before publish, no manufacturer table |

---

## 12. Delivery Roadmap (§10) & MVP Boundary (§11)

| Phase | Done? |
|---|---|
| Discovery/UX (2w) | Docs present, no Figma — **50%** |
| Platform foundation (3w) tenant/auth/RBAC/domains/CI | **65%** — tenant/auth done, domains/RBAC partial, CI exists but preview not verified |
| Commerce MVP (5w) catalog/inventory/storefront/cart/checkout/orders/payments | **62%** — core flow done, discounts/COD/invoices missing |
| Theme/SEO (3w) blocks/themes/metadata/structured/sitemaps | **60%** — themes/page-builder code + SEO meta/sitemap generator, but no block persistence/API |
| Automation (4w) IG/WA/webhooks/rules/checkout links | **52%** — engine + webhooks real, OAuth persist missing, many actions stub |
| CRM/analytics (4w) leads/timeline/attribution/funnel/dashboard | **56%** — leads/customers/conversations real, timeline/aggregates broken |
| Hardening/pilot (3w) security/perf/compliance/pilot | **35%** — rate limit/idempotency/sentry done, audit/DPDP/terraform missing |

**MVP boundary:** one country/one currency/one payment/one shipping, 3-5 presets, guest checkout, basic discounts, IG keyword, simple dashboard — **MVP ~68% shippable** (presets: `packages/themes/src/index.ts:241` has 3: default/minimal/vibrant; guest checkout real; discounts broken; IG keyword trigger real; dashboard real but net_sales hard-coded).

---

## 13. Missing vs Partially Implemented — Aggregated List

### 🔴 Missing (0% — no code)
1. `infrastructure/terraform/*` — no `.tf` (`find *.tf` empty)
2. Downloadable invoices — no `Invoice` model, no `GET /orders/{id}/invoice`
3. COD — no provider/status
4. Audit logs — no model/middleware
5. Bot protection (Turnstile/reCAPTCHA)
6. S3 media + CDN — no S3 client, `packages/integrations` no S3
7. DPDP export/delete/consent withdrawal endpoints (only markdown)
8. Backups/PITR/DR
9. Visual drag-and-drop editor (correctly deferred per §11)
10. Theme/page API (`apps/api/modules/page`, `theme`)
11. Campaign model (analytics campaign performance)
12. Manufacturer/return-policy evidence gate
13. `POST /checkout/{id}/pay` exposure (initiate payment)

### 🟡 Partially Implemented (1-75% — code exists but stub/bug/mismatch)
| # | Area | % | Symptom | File |
|---|---|---|---|---|
| 1 | Discounts | 15% | `DiscountCode` undefined, checkout 10% hard-coded | `packages/commerce/src/infalette_commerce/discounts.py:1`, `checkout.py:123` |
| 2 | Inventory confirm | 10% | `confirm_inventory_deduction: pass` | `packages/commerce/src/infalette_commerce/inventory.py:34` |
| 3 | Analytics aggregates | 25% | `aggregator.py:35` writes `metrics_json` vs `metric_daily.value`, worker imports wrong class | `packages/analytics/src/infalette_analytics/aggregator.py:35`, `apps/workers/tasks/analytics.py:44` |
| 4 | SocialIdentity tenant | 30% | no `tenant_id`, webhook `provider` vs `platform` mismatch | `models/social_identity.py:30`, `instagram/webhook.py:259` |
| 5 | OAuth persist | 5% | `store_tokens` logs only | `packages/integrations/src/infalette_integrations/oauth.py:170` |
| 6 | Idempotency replay | 45% | caches empty body, brittle path match | `apps/api/core/idempotency.py:98` |
| 7 | Tenant isolation | 55% | `cart` PUT/DELETE, `order` 6/9, `store` 3/5 missing tenant filter; no RLS | `apps/api/modules/cart/routes.py:63`, `order/routes.py:122`, `infrastructure/docker/postgres/init.sql:1` |
| 8 | Feature flags | 55% | only automation gated, quotas never checked | `apps/api/core/feature_flags.py:1` |
| 9 | Page builder persistence | 20% | `blocks_json` never via API, storefront renders hard-coded grid | `packages/page-builder/src/index.ts:1`, `apps/storefront/app/[tenant]/page.tsx:1` |
| 10 | CRM timeline | 25% | events recorded but no `GET /leads/{id}/timeline` | `models/event.py`, `apps/api/modules/lead/routes.py:97` |
| 11 | Payment per-tenant linked | 20% | single platform key, no linked account | `packages/integrations/src/infalette_integrations/razorpay/client.py:124` |
| 12 | Shipping/tax | 55% | hard-coded rates/tax, no live carrier | `packages/commerce/src/infalette_commerce/shipping.py:103`, `tax.py:85` |
| 13 | Lead stage drift | 60% | `stage` enum vs `status` string vs `alembic.status` | `models/lead.py:60`, `alembic/001_initial_schema.py:224-239` |
| 14 | MFA wiring | 40% | code real, no auth route UI | `packages/auth/src/infalette_auth/mfa.py:63` |
| 15 | Webhook HMAC mismatch | 75% | Razorpay `str(payload)` vs `json.dumps sort_keys` | `razorpay/client.py:124` vs `razorpay/webhook.py:231` |
| 16 | Media S3 | 20% | no S3, image as `image_url` string | `models/product.py:100` |
| 17 | Tests | 20% | 14 tests, wrong signatures, e2e empty, no Vitest/Playwright | `tests/integration/*.py`, `tests/e2e/conftest.py:8`, `tests/performance/` empty |
| 18 | Monitoring Otel | 45% | YAML exists, never `instrument_fastapi` | `infrastructure/monitoring/otel-collector.yaml:1`, `apps/api/main.py:127` |
| 19 | Storefront SEO | 60% | sitemap now added but `canonical_url`/`redirects` missing | `packages/seo/src/infalette_seo/sitemap_generator.py` |

---

## 14. Bottom Line

- **To prove Store-plan with 3 pilots (per My strongest recommendation §11), you need ~4-6 weeks fixing P0 partials:** discounts table + checkout 10% removal, inventory confirm + schema align, `POST /checkout/{id}/pay` + invoice stub, page/theme API (or at least `GET/PUT /pages`), SocialIdentity tenant_id fix + OAuth persist, analytics aggregator fix, tenant-isolation filters, idempotency body caching, and Playwright smoke. Those are all currently partially implemented but not pilot-blocking logic errors.
- **To claim “fully built” per §10 (20-24w), you are ~58% there:** commerce/analytics/automation skeletons exist, but security/compliance/infra/testing/hardening are the long tail (§9 alone is <45%).
- Frontend API-wiring is the one area that *is* near 90% after 2026-08-22 (verified `next build` 15+9+4 routes, 0 mocks via grep) — the remaining 58% overall is backend correctness, not frontend mocks.
