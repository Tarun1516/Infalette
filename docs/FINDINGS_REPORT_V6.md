# Infalette — Independent Audit & Gap Report v6

**Date:** 2026-08-24
**Method:** Fresh independent audit against `docs/requirements.md` (all prior reports ignored as self-assessments). Evidence: line-by-line code reads by 6 parallel auditors + direct execution (`pytest`, `smoke_api.py`, `next build`, import probes, ORM-construction probes, frontend↔backend contract cross-checks). Every finding below was **verified by direct execution or file citation** in this session.

> ## ✅ CLOSURE STATUS (same session, post-fix pass)
>
> All four phases of the closure plan have been implemented and verified:
> **120 tests pass** (was 99; +21 new regression tests covering every fixed chain) · smoke 13/13 · all three `next build`s pass · alembic single-head at `010_shopper_social_identity` · 8 celery-beat jobs · every API module and worker imports cleanly.
>
> | Phase | Findings closed |
> |---|---|
> | P1 — critical chains | C1–C9: public catalog endpoints + storefront rewiring; address aliases; conversation model fix (single Message table); webhook-replay idempotency guard; store settings columns mapped; category/collection/automation-rule ORM fixes; migration drift closed in 009; /platform/plans+/subscriptions + /tenants/onboard |
> | P2 — automation & CRM | keyword gating evaluated (M1); private_reply/product_recommendation/schedule_reminder/lead_create/tag_lead actions (M2); checkout.unpaid beat task with dedupe (M3); WA webhooks → events + automation + lead link + dedup (M4); SocialIdentity.customer_id migration+model (M14); campaign/agent/customer on lead create (M15); event-driven stage progression listener (M16); consent gate on recovery emails + automation sends (M17); raw-body Meta HMAC enforced (M18); IG/WA dedup (M19); per-tenant token resolver used by sends (M20) |
> | P3 — analytics | dashboard route returns full metric set incl. repeat-customers & low-inventory with exact frontend key contract (M5); product.viewed via public /track + storefront SSR call, conversation.message_received persisted from IG+WA handlers (M6); source+lead/customer ids stamped into checkout/payment events; attribution join keys live (M7); abandoned-social resolves social hints (M8); FUNNEL_FULL + ADVANCED_DASHBOARD tier gates; campaigns gated (M26) |
> | P4 — polish | variant-aware transactional inventory reserve w/ compensation + flush-fixed release (M21/M22); checkout-expiry restock beat job; category_grid/bundles blocks rendered; custom-html removed from page-builder (spec violation); SSR + Product JSON-LD + safety info on product pages (M24); weekly-frequency honored + CSV delivered for scheduled reports; Reports UI page; pip-audit/pnpm-audit CI job; cart sale-price consistency; order-cancel restock; coupon consumed at payment |
>
> Residual (deployment-env only, not code): Lighthouse numbers on live infra, live carrier shipping rates, executed load baseline.

---

## Original audit (pre-fix)



## Headline numbers

| Category | Complete | Partial | Missing | Category % |
|---|---|---|---|---|
| 1. Tenant & storefront mgmt | | domain verify, themes/presets, page blocks | store settings persistence, plans/subscriptions API, platform-admin tenant create, public catalog endpoints | **45%** |
| 2. Catalog & inventory | product CRUD+variants+media, reserve/release | variant inventory not deducted; admin pagination/search ignored | category↔product link broken at runtime; collection fields missing | **55%** |
| 3. Checkout & orders | cart, checkout totals, COD, invoices, coupons | shipping zones hardcoded; refund never calls provider | storefront checkout 422s; cart qty PATCH mismatch; duplicate orders on webhook replay; refunds endpoint 405 | **50%** |
| 4. Social automation | rules CRUD, engine, WA flow→checkout bridge, OAuth persist+refresh job | IG HMAC re-serialization; no dedup; global-not-tenant tokens | keyword matching never evaluated; conversation module 500s (import); private-reply/recommendation/reminder actions missing; checkout.unpaid never emitted | **40%** |
| 5. CRM | customers/leads CRUD, campaigns perf, consent endpoint, timeline endpoints | LTV partial; timeline misses payment/message events | conversation↔customer link absent; SocialIdentity has no customer_id; lead stage dropdown calls 404; CSV import wrong path/format; campaign_id never settable at create | **45%** |
| 6. Analytics | top-products, sales series data, funnel/attribution/abandoned endpoints exist | aggregates written but never read | dashboard returns 4 counters vs 13 required metrics (rich DashboardService dead code); frontend key mismatches blank out KPI tiles; product.viewed & conversation.message_received events never persisted → funnel stages always 0; attribution always "unknown"; abandoned-social segment structurally empty | **40%** |
| 7. Security & compliance | JWT+MFA routes, RBAC, rate-limit, idempotency, audit middleware, bot protection, RLS policies, DPDP export/delete endpoints, webhook sig for payments | Meta webhook sig optional + wrongly canonicalized; Stripe timestamp tolerance | dependency scanning absent (no dependabot/pip-audit); consent not enforced before follow-ups; automation execution_limit unused | **70%** |
| 8. Storefront & SEO | tenant home SSR + metadata + JSON-LD, sitemaps, robots, guest cart UX | products list/detail are CSR without metadata/markup; block renderer missing category_grid+bundles; page-builder enum diverges from spec's 10 blocks (+custom-html violates spec) | anonymous fetches to auth-required APIs → catalog/cart pages render empty; custom-domain→tenant resolution unwired in storefront | **35%** |
| 9. Architecture & infra | modular monolith clean, Terraform modules, docker-compose, OTel/Sentry wired, CI runs tests | seo_pages/subscriptions tables lack ORM models; leads.stage & customers.metadata_json drift vs migrations | — | **75%** |

**Weighted overall: ≈ 48–52% complete. Fully working end-to-end ≈ half the surface; ~35% partially implemented; ~15% effectively missing (broken chains).**

*(The earlier GAP_REPORT/FINAL_PRODUCTION_REPORT claims of 90–99% did not hold up under execution-level verification; do not treat them as current state.)*

---

## CRITICAL (app-breaking chains, must fix first)

| # | Finding | Evidence |
|---|---|---|
| C1 | **Storefront renders empty**: home/products/pages fetched with only `X-Tenant` but `/products`, `/stores`, `/pages`, `/categories` require Bearer auth → 401 → `.catch(()=>null)` → blank catalog | `apps/api/modules/product/routes.py:34,47`; `apps/storefront/app/[tenant]/page.tsx:10-14`; verified: smoke test shows `products unauthed -> 401` |
| C2 | **Storefront checkout 422s**: form sends `{address, pincode}`; `AddressSchema` requires `line1`, `postal_code` → every UI checkout fails validation | `apps/storefront/components/checkout/checkout-form.tsx:32-33`; `packages/validation/src/infalette_validation/schemas.py:274-296`; `apps/storefront/app/[tenant]/checkout/page.tsx:29` |
| C3 | **Conversation module dead**: `services.py:13` imports nonexistent `models.conversation_message` → ModuleNotFoundError → ALL `/conversations/*` endpoints 500 (inbox unusable). Also constructs Conversation with non-existent columns `customer_id/assigned_to/metadata_json` and `"web"` vs enum `"website"` | import probe failed this session; `apps/api/modules/conversation/services.py:13,30-45`; model `conversation.py` |
| C4 | **Duplicate orders on webhook replay**: `_confirm_checkout` has no paid-guard — Razorpay retries (they retry on timeout) create a second Order each time; also inventory deducted twice | `packages/commerce/src/infalette_commerce/checkout.py:495-560` |
| C5 | **Admin settings silently drop data**: Store model lacks `custom_domain/logo/logo_url/currency/tax_rate/theme_config` columns; `update_store_settings` setattr-with-hasattr drops them while UI says "Settings saved" | probe: all `hasattr(Store,…)` False this session; `apps/api/modules/store/services.py:127-169`; migration 001 HAS the columns — ORM never mapped |
| C6 | **Category/collection creation crashes**: services pass `seo_title/sort_order/status/product_ids/rules` kwargs that don't exist on models; Product has NO `category_id` so products can't belong to categories at all | probe failed this session; `apps/api/modules/category/services.py:52-62,112`; `collection/services.py` |
| C7 | **Automation rule creation crashes**: service always passes `conditions=` kwarg; AutomationRule doesn't map it (migration has column, ORM doesn't) → TypeError on every POST /automation with conditions | probe failed this session; `apps/api/modules/automation/services.py:59`; `models/automation_rule.py` |
| C8 | **Leads.stage / customers.metadata_json drift**: ORM maps columns that no migration creates → any Lead INSERT or Customer INSERT fails with UndefinedColumn on an alembic-managed Postgres (tests pass only because create_all) | `models/lead.py` `_stage=Column("stage",…)`, hybrid setter always writes it; grep of migrations 001-008 confirms absence |
| C9 | **Platform-admin tenant create 422s**: form sends `{name,slug,plan}`; `TenantCreate` requires `{name, plan_id(UUID), admin_email, admin_password}`; no `/plans` or `/subscriptions` endpoints exist (UI catches errors, renders empty) | `apps/platform-admin/app/tenants/page.tsx:12,38`; `schemas.py:168-174`; main.py router list |

## MAJOR (feature-defining gaps)

| # | Finding | Evidence |
|---|---|---|
| M1 | **Keyword matching never evaluated**: comment_keyword rules map to event types only; conditions skipped when trigger_config lacks event_type → rule fires on EVERY message | `packages/automation/src/infalette_automation/triggers.py:37,90-105` |
| M2 | **Spec actions missing**: no private_reply (IG), no product_recommendation, no reminder scheduling actions; checkout_link action needs customer_id/cart_id payload that webhook TriggerEvents don't carry → returns "" | `packages/automation/src/infalette_automation/actions.py` ACTION_TYPES |
| M3 | **checkout.unpaid trigger can never fire**: nothing emits the event; beat has no reminder task; recover-abandoned-carts is cart/email only | grep zero producers; `workers/main.py` beat list |
| M4 | **WA messages bypass automation & analytics**: whatsapp webhook records neither Event rows nor TriggerEvents → social funnel stage 1 = 0, processor loop sees nothing, WA automations never run | `packages/integrations/.../whatsapp/webhook.py:100-166` |
| M5 | **Analytics dashboard contract broken**: `/analytics/dashboard` returns 4 counters; rich DashboardService (gross/net/AOV/refunds/conversion/repeat/low-inventory) is dead code; admin reads keys that don't exist → tiles show ₹0/—; sales-over-time reads `sales.series` but backend returns bare array | `apps/api/modules/analytics/services.py:20-70`; `dashboard.py` unrouted; `apps/admin/app/analytics/page.tsx:74-106` |
| M6 | **Funnel stages permanently 0**: `product.viewed` and `conversation.message_received` Event rows never persisted anywhere; reply-stage counts outbound Message rows that automation sends never create | `funnel.py:33,114-137`; grep zero emitters |
| M7 | **Channel attribution always "unknown"**: checkout.created payload lacks `source`; attribution_json hardcodes website; automation-created checkouts emit no event | `checkout.py:218-246`; `dashboard.py:135-146` |
| M8 | **Abandoned-social segment structurally empty**: queries lead_id inside checkout.created/payment.succeeded payloads which emitters never include | `analytics/services.py:252-300` vs `checkout.py:241-247,481-487` |
| M9 | **Refund button 405**: admin POSTs `/orders/{id}/refunds`; backend only has `POST /orders/refunds` requiring payment_id; provider refund API (RazorpayClient.create_refund/Stripe) exists but is never called — money never actually returned | `apps/admin/lib/api.ts:192`; `apps/api/modules/order/routes.py:92`; grep zero callers |
| M10 | **Cart qty update method mismatch**: frontend PATCH `/cart/items/{id}`, backend PUT-only with query param → quantity stepper fails | `apps/storefront/lib/api.ts:82`; `cart/routes.py:80` |
| M11 | **Lead stage dropdown 404**: admin PATCHes `/leads/{id}/stage`; backend has only PATCH `/leads/{lead_id}` | `apps/admin/lib/api.ts:274-276`; `lead/routes.py` route list |
| M12 | **CSV import broken twice**: multipart to `/leads/import` vs backend JSON `/leads/bulk-import` | `api.ts:278-287`; `lead/routes.py:114` |
| M13 | **Assign conversation param mismatch**: body `{user_id}` vs query param `agent_id: UUID` → 422 | `api.ts:241-242`; `conversation/routes.py:81-87` |
| M14 | **SocialIdentity ≠ shopper identity**: table stores tenant OAuth tokens only; no customer_id → person cannot be unified across web/IG/WA (spec §7 row violated). Webhook leads get fabricated emails (`{user}@instagram.com`) never linked to customers | `models/social_identity.py`; `instagram/webhook.py` |
| M15 | **Campaign attribution decorative**: `create_lead` ignores campaign_id; nothing captures UTM; orders carry no campaign/source → campaign performance always zeroes | `lead/services.py:63-74`; `checkout.py:218-222` |
| M16 | **Stage transitions not event-driven**: nothing advances lead stage on payment.succeeded/checkout.created/order.fulfilled; spec pipeline is event-driven | grep across processors/workers |
| M17 | **Consent not enforced before follow-up**: abandoned-cart emails and automation sends never check consent_json (spec: follow-up only where consent permits) | `workers/tasks/abandoned.py`; `actions.py` send paths |
| M18 | **Meta webhook signature weak**: IG verifies re-serialized `json.dumps(sort_keys)` instead of raw body (real Meta payloads fail), and verification is skipped when header absent; WA inbound never verifies | `instagram/webhook.py:56-70`; `inbound.py:48-51` |
| M19 | **No webhook dedup**: `deduplicate_events/messages` exist but are never called; WA messages stored without external_id → replays create dup conversations/messages | `instagram/webhook.py`; `whatsapp/webhook.py:124-127` |
| M20 | **Tenant tokens unused for sending**: WhatsApp/Instagram clients read global env tokens; per-tenant SocialIdentity access_token never passed → multi-tenant sending impossible | `whatsapp/client.py:21-24`; `instagram/client.py:25-35` |
| M21 | **Variant inventory never reserved/deducted**: reserve path touches Product only; CartItem.variant_id accepted but ignored by inventory logic | `commerce/inventory.py`; `checkout.py` reserve loop |
| M22 | **Inventory not transaction-safe on partial failure**: reserve commits per-item mid-loop; failure on item N leaves items 1..N-1 deducted; no expiry job releases expired checkouts' reservations | `checkout.py` create_checkout; workers have no expiry task |
| M23 | **Block renderer incomplete**: storefront renders 8/10 block types; category_grid & bundles fall to raw `<pre>` dump; page-builder package enum diverges from spec's 10 blocks and includes custom-html (spec forbids arbitrary code) | `apps/storefront/app/[tenant]/page.tsx` renderBlocks; `packages/page-builder/src/index.ts` |
| M24 | **Product pages have no SEO**: products list/detail are `"use client"` CSR — no generateMetadata, no Product JSON-LD, though every plan is sold with "SEO and Google product markup" | `apps/storefront/app/[tenant]/products/**` |
| M25 | **Scheduled reports frequency ignored**: weekly schedules run daily; recipients get outcome-dict dump not CSV; schedules/abandoned-segments have zero UI (api methods unused) | `workers/tasks/exports.py:233-258`; grep admin app |
| M26 | **Plan tiers collapsed**: FUNNEL_ANALYTICS identical for Limited & Full; SALES_DASHBOARD same Basic & Advanced; campaigns router entirely ungated | `core/feature_flags.py` PLAN_FEATURES; `campaigns/routes.py` |

## MINOR

- Admin products/orders/customers pagination+search params silently ignored by backend list endpoints.
- Cart total uses price_cents while checkout uses sale_price_cents → displayed totals diverge when sale active.
- Coupon usage incremented at checkout creation (pre-payment) — abandoned checkouts burn coupon limits.
- Shipping zones parameter unused; rates hardcoded module constants (not tenant-configurable).
- OrderItem snapshot lacks effective tax amount; invoice recomputes tax from current rates (spec wants immutable tax snapshot).
- Order cancel doesn't restock; returns flip status regardless of transition validity.
- COD payment stays PENDING forever (no mark-on-delivery path).
- Stripe webhook timestamp tolerance unchecked.
- OAuth refresh worker hits wrong IG endpoint (`api.instagram.com/oauth/access_token` vs `graph.instagram.com/refresh_access_token`).
- No dependabot/pip-audit/pnpm-audit anywhere in CI (spec §9 dependency scanning).
- `seo_pages`/`subscriptions` tables have no ORM models.
- Customer detail page never calls the timeline endpoint it displays a section for; consent field name mismatch (`consent` vs `consent_json`).
- Funnel rate math misbehaves on zero-count stages.
- Storefront account/invoice endpoints require staff JWT — customer tokens can't download their own invoice.
- Custom-domain→tenant resolution exists server-side but storefront has no host-based tenant mapping (only `[tenant]` path).

---

# Closure Plan (ordered)

**Phase 1 — Unbreak the core chains (C1-C9):**
1. Public catalog/store/page/category read endpoints (tenant-scoped, no auth) + storefront uses them; keep admin on authenticated ones.
2. Fix address schema contract (accept address→line1, pincode→postal_code via aliases) OR align form; fix cart PATCH↔PUT; align refund endpoint; align lead stage/import/assign contracts.
3. Create `conversation_message` model fix → single Message model used everywhere; add missing Conversation columns via migration; fix channel enum.
4. Idempotent `_confirm_checkout` (paid-guard + unique order per checkout).
5. Map missing Store columns (custom_domain/logo/currency/tax_rate/theme_config) in ORM + migration alignment; settings round-trip test.
6. Add `category_id` to products + missing Category/Collection columns; fix AutomationRule conditions/actions mapping; add leads.stage + customers.metadata_json to migration 009; add ORM models for subscriptions/seo_pages or drop tables.
7. Platform-admin: implement `/plans` + `/subscriptions` endpoints; fix create-tenant flow (resolve plan slug→id, create owner user).

**Phase 2 — Make automation & CRM real (M1-M4, M14-M20):**
8. Evaluate rule conditions incl. keywords; add private_reply/product_recommendation/schedule_reminder actions; emit checkout.unpaid from beat task; wire WA webhooks into automation + event recording; per-tenant token usage; webhook dedup + raw-body HMAC.
9. SocialIdentity.customer_id (migration) + shopper identity linking in webhooks; set campaign_id at lead create; UTM capture on storefront→checkout; event-driven stage progression listener; consent checks before all outbound.

**Phase 3 — Analytics that tells the truth (M5-M8, M25-M26):**
10. Wire DashboardService through `/analytics/dashboard` returning the full metric set; fix frontend key contract; emit product.viewed from storefront SSR + conversation.message_received from webhook paths; include source in checkout.created payload + emit for automation checkouts; carry lead_id/customer_id in checkout/payment events; read charts from MetricDaily with raw fallback; enforce Limited/Full & Basic/Advanced gating + gate campaigns.

**Phase 4 — Catalog/SEO/hardening polish (M21-M24 + minors):**
11. Variant-aware inventory reservation; transactional reserve w/ compensation + checkout-expiry release job; complete block renderer + align page-builder enums; SSR + Product JSON-LD + metadata on listing/detail; scheduled-report frequency + CSV delivery + Reports UI; dependency scanning in CI.

**Definition of done:** new integration tests for every fixed chain (storefront-anonymous catalog, UI-shaped checkout payload, webhook replay, settings round-trip, rule-with-keywords firing, funnel>0 after simulated journey), full suite green, all three builds green, smoke extended to cover the new public endpoints.
