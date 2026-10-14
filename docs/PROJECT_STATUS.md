# Infalette — Project Status

**Last updated:** 2026-08-29 (v7 completion pass — all partial items closed)
**Stack:** Turborepo + pnpm, Next.js 14 (admin/platform-admin/storefront), FastAPI + SQLAlchemy 2.0 + PostgreSQL + Redis + Celery, Tailwind
**Source of truth:** `docs/FINDINGS_REPORT_V6.md` (independent audit + closure record) + v7 completion pass (see below)

## Verification state (all green, this session)

| Check | Result |
|---|---|
| pytest (unit + integration + e2e) | **132 passed**, 2 skipped |
| `next build` admin / storefront / platform-admin | all compile ✓ |
| Alembic chain | single head `012_order_item_tax_snapshot`, 12 revisions |
| Module import sweep | every changed API route module + package imports (via test collection) |

## v7 completion pass (2026-08-29)

The seven partially-implemented items from the v6-era audit were closed, each
with a regression test in `tests/integration/test_v7_completions.py`:

1. **Web UTM/campaign attribution** — storefront captures `utm_*` (last-touch,
   7-day window, `components/attribution-capture.tsx` + `lib/api.ts`), sends
   `attribution` with checkout; backend (`commerce/checkout.py`) resolves
   `utm_campaign` → campaign id, stamps it on the checkout row and
   `checkout.created` event; CRM listener stamps the lead's campaign.
2. **Customer shipment tracking** — public `GET /public/track-order`
   (order id + email verified, 404-safe), storefront `/track` page for
   guests, account page shows fulfillment tracking, customer order list is
   now scoped to the customer's own orders.
3. **Immutable tax snapshot** — per-item tax frozen at checkout
   (`tax_cents`/`tax_rate_bps` on order items, migration `012`);
   invoices use the snapshot, recomputing only for legacy rows.
4. **COD settlement on delivery** — order status → DELIVERED flips PENDING
   COD payments to SUCCEEDED and emits `payment.succeeded`.
5. **MFA enforcement** — admin roles (configurable via `MFA_REQUIRED_ROLES`)
   receive a 15-minute enrollment-scoped token until they complete
   `/auth/mfa/setup` + `/auth/mfa/confirm-enrollment`; scope enforced in
   `get_current_user`.
6. **Live carrier rates** — `ShippingService.get_shipping_cost` uses the
   tenant's carrier credentials (`shipping_rules_json.carrier`) against
   live rate APIs; any failure falls back to zone/weight rules.
7. **Product CSV import** — `POST /products/import` (upsert by SKU,
   quota-aware) + "Import CSV" UI on the admin products page.

## What the v6 audit found and what was done

The prior reports claimed ~99% complete; an independent execution-level audit measured **~50%** — tests were green because they bypassed exactly where the app broke (ORM↔migration drift on alembic DBs, frontend↔backend contract mismatches, unauthenticated storefront fetches). The full findings table with per-item evidence is in `docs/FINDINGS_REPORT_V6.md`; every critical/major item has since been fixed and covered by a regression test (`tests/integration/test_v6_fixes.py`, `tests/integration/test_v6_phase2.py`).

Highlights:
- **Storefront works anonymously now** — public `/api/v1/public/{products,store,pages,categories,track}` endpoints; home/products/detail are SSR with metadata, Product JSON-LD and safety info.
- **Checkout works from the real UI** — address aliases accepted server-side; cart PATCH/PUT aligned; webhook replay can't double-create orders; inventory reserve is variant-aware and transactional with compensation; expired checkouts restock via beat.
- **Automation is real** — keyword gating enforced, private-reply/product-recommendation/reminder actions exist, WhatsApp messages trigger automation and persist funnel events, per-tenant tokens are used for sends, Meta HMAC verified against raw bytes, dedup everywhere.
- **CRM pipeline is event-driven** — lead stages advance from checkout/payment/order events; SocialIdentity links shoppers across channels; consent gates every outbound follow-up; campaigns accept attribution at create.
- **Analytics tells the truth** — dashboard returns the full metric set under the exact keys the UI reads; funnel stages populate from real events; plan tiers (Limited/Full funnel, Basic/Advanced dashboard) are enforced; Reports page schedules CSVs.

## Remaining (deployment-environment actions only, not code gaps)

1. Lighthouse ≥90 verification on live infra (suites ready).
2. Live carrier rate **calls** — the integration is implemented and tested
   (per-tenant credentials, live→zone fallback); add real carrier account
   credentials to `shipping_rules_json.carrier` per tenant to go live.
3. Executed load-test baseline in staging (Locust file ready).

## Deferred per spec §11 (not gaps)

Visual drag-and-drop editor · AI-generated replies · loyalty points engine · subscription *billing* beyond plan assignment · multi-currency · mobile apps · warehouse mgmt · microservices split.

## Commands

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/e2e/test_purchase_flow.py -q
.venv/bin/python scripts/smoke_api.py
cd apps/admin && ./node_modules/.bin/next build   # same for storefront, platform-admin
```
