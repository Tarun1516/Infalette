# Baby e-commerce platform

## The right product model

Build this as a **multi-tenant, headless commerce SaaS**, not separate websites sharing copied code. Every influencer gets a tenant with their own domain, products, payment account, social accounts, theme configuration and analytics, while one platform handles commerce, automation, SEO and CRM.

The big rule: **never fork the frontend per client**. Create reusable page sections, design tokens and theme presets that can be configured into genuinely different storefronts.

---

# 1. Product definition

**Working product:** A white-label social commerce platform for influencers selling pregnancy, postpartum, baby and childcare products.

**Primary users:** Influencers, D2C brands working with influencers, their operations teams and shoppers.

**Business model:** Monthly subscription by plan, optional setup/design fee, usage charges for messaging, and potentially a platform fee per transaction.

### User roles

| Role | Capabilities |
| --- | --- |
| Platform owner | Manage tenants, subscriptions, templates, integrations and platform health |
| Tenant owner | Manage the influencer’s store, team, billing and connected accounts |
| Store manager | Products, inventory, orders, discounts and content |
| Marketing agent | Campaigns, social automations, leads and CRM |
| Support agent | Conversations, customers, orders, returns and notes |
| Customer | Browse, purchase, track orders and manage consent |

---

# 2. Plans and entitlements

| Capability | Store | Store + Automation | Store + Automation + CRM |
| --- | --- | --- | --- |
| Custom storefront and domain | Yes | Yes | Yes |
| Products, variants and inventory | Yes | Yes | Yes |
| Cart, checkout and payments | Yes | Yes | Yes |
| Orders, shipping and refunds | Yes | Yes | Yes |
| SEO and Google product markup | Yes | Yes | Yes |
| Instagram comment and DM integration | No | Yes | Yes |
| WhatsApp commerce automation | No | Yes | Yes |
| Automated checkout links | No | Yes | Yes |
| Unified social inbox | No | Yes | Yes |
| Customer and lead profiles | Basic | Basic | Full |
| Funnel analytics | No | Limited | Full |
| Abandoned-DM and abandoned-cart segments | No | Limited | Yes |
| Sales dashboard and attribution | Basic | Basic | Advanced |
| CSV exports and scheduled reports | No | No | Yes |

Implement these through **feature flags and quotas**, not three separate applications.

---

# 3. PRD

## Product goal

Allow an influencer to launch a branded commerce website, sell products and convert social conversations into trackable orders without requiring a new codebase for every influencer.

## Success metrics

| Metric | Initial target |
| --- | --- |
| Client onboarding time | Under 2 business days |
| Storefront Lighthouse performance | 90+ on core pages |
| Store uptime | 99.9% |
| Checkout conversion | Measured per tenant and channel |
| DM-to-checkout creation rate | 20%+ for qualified conversations |
| Checkout-to-paid conversion | 40%+ from generated checkout links |
| Order attribution coverage | 90%+ |
| Store customization without code | 95% of client requests |

## Core functional requirements

### Tenant and storefront management

Each tenant must support a custom domain, subdomain, logo, typography, colors, menus, legal pages, social links, payment account, shipping rules and SEO defaults.

The page builder should use controlled blocks such as hero, featured products, category grid, testimonials, influencer story, video, FAQ, bundles, newsletter and Instagram gallery. Clients configure the blocks, but cannot insert arbitrary code.

### Catalog and inventory

Products need categories, collections, variants, SKU, price, sale price, tax class, dimensions, inventory, images, ingredients/materials, safety information, age suitability and pregnancy/postpartum stage.

Inventory changes must be transaction-safe. Never reduce stock based only on adding an item to the cart; reserve it when checkout begins and confirm deduction after payment.

### Checkout and order management

Support guest checkout, customer accounts, coupons, shipping calculation, taxes, online payment, cash on delivery where appropriate, order confirmation, shipment tracking, cancellations, returns, refunds and downloadable invoices.

Each influencer should receive funds through their own connected merchant account. For India, Razorpay with linked accounts is a practical starting point; use Stripe Connect for supported international markets.

### Social automation

A tenant connects an eligible Instagram Professional account and/or WhatsApp Business account through OAuth. Incoming messages, comments and webhook events are normalized into a common conversation model.

Automation triggers can include:

- A comment contains “buy”, “price”, “link” or a configured keyword.
- A customer sends a product name or SKU by DM.
- A customer responds to a story or campaign.
- A WhatsApp user submits a structured product-selection Flow.
- A generated checkout remains unpaid after a configured interval.

Automation actions include private reply, product recommendation, checkout-link generation, lead creation, assignment to an agent, reminder scheduling and tagging.

**Important limitation:** Instagram is not an unrestricted bot channel. Conversations generally begin through user activity, and a private reply to a commenter is constrained by Meta’s rules. Do not promise clients that the platform can spam every follower or run unlimited outbound DMs.

### CRM

The CRM should represent a person across website, Instagram and WhatsApp where identity can be lawfully matched. Each profile contains contact information, consent, social identities, orders, lifetime value, conversations, tags, lead stage and timeline events.

Recommended lead stages:

`New Lead → Engaged → Product Selected → Checkout Created → Paid → Fulfilled → Repeat Customer`

“DM but did not buy” should be calculated from events, not manually entered:

1. The person sends a message or responds to an automation.
2. A lead and conversation are created.
3. A product or checkout is associated with that lead.
4. If no paid order appears within the attribution window, the lead becomes an abandoned social checkout.
5. Follow-up happens only where channel rules and consent permit it.

### Analytics dashboard

The advanced dashboard should show gross sales, net sales, orders, refunds, average order value, conversion rate, repeat customers, top products, low inventory, sales over time, channel attribution and campaign performance.

Social funnel reporting should show:

`Comment/DM → Reply → Product viewed → Checkout created → Payment started → Paid`

Store both the raw event and daily aggregate tables. Running every chart directly against orders and message history will become painfully slow.

---

# 4. High-level architecture

```
Customers
   |
   v
CDN / Edge / Web Application Firewall
   |
   +---- Tenant storefront: custom domain resolved to tenant
   |
   +---- Admin and CRM dashboard
              |
              v
          API Gateway
              |
    +---------+---------+---------+----------+
    |         |         |         |          |
 Identity  Commerce  Content  Automation  Analytics
    |         |         |         |          |
    +---------------- PostgreSQL ------------+
              |              |
            Redis        Event/Job Queue
                              |
                +-------------+-------------+
                |             |             |
          Meta APIs      Payments       Email/SMS
       Instagram/WA   Razorpay/Stripe   Notifications
```

Start with a **modular monolith**, not microservices. Separate modules and events cleanly so high-volume automation and analytics workers can be extracted later, but deploying twelve services before product-market fit is architecture cosplay.

## Tenant isolation

Every tenant-owned database record must contain `tenant_id`. Tenant context is resolved from the domain or authenticated account and enforced in the data-access layer.

For the first release, use shared PostgreSQL tables with tenant-scoped indexes and row-level security where practical. Large enterprise tenants can receive dedicated databases later.

## Event model

Useful domain events include:

```
tenant.created
storefront.published
product.updated
inventory.changed
cart.abandoned
checkout.created
payment.succeeded
payment.failed
order.fulfilled
message.received
comment.received
automation.triggered
lead.stage_changed
customer.consent_changed
```

Events drive notifications, CRM timelines, analytics and automation without tightly coupling every module.

---

# 5. Recommended tech stack

| Layer | Recommendation |
| --- | --- |
| Monorepo | Turborepo with pnpm |
| Storefront | Next.js, React, TypeScript |
| Admin dashboard | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| Page customization | JSON-based blocks, design tokens and validated theme schemas |
| Backend | Python with REST APIs and OpenAPI |
| Database | PostgreSQL |
| ORM | Prisma |
| Cache/session/rate limits | Redis |
| Background jobs | BullMQ initially |
| Product search | PostgreSQL search first, OpenSearch only when scale requires it |
| Media | S3-compatible object storage plus CDN |
| Authentication | Auth.js or managed identity, with tenant RBAC and MFA for admins |
| Payments | Razorpay for India, Stripe/Stripe Connect internationally |
| Social | Instagram Messaging API, Instagram webhooks, WhatsApp Cloud API and Flows |
| Email | Amazon SES or Postmark |
| Analytics | PostHog for product analytics, warehouse later |
| Error monitoring | Sentry |
| Observability | OpenTelemetry, structured logs and managed metrics |
| Infrastructure | AWS ECS/Fargate or Kubernetes only after scale justifies it |
| CI/CD | GitHub Actions, preview environment per pull request |
| Infrastructure as code | Terraform |
| Testing | Vitest/Jest, Playwright and contract tests for integrations |

For SEO, Next.js server rendering plus correct metadata is enough. You do **not** need a mysterious separate “SEO engine”; you need canonical URLs, structured data, sitemaps, redirects, strong content controls and fast pages.

---

# 6. Suggested repository structure

```
social-commerce-platform/
├── apps/
│   ├── storefront/              # Public multi-tenant storefront
│   ├── admin/                   # Tenant admin, CRM and analytics
│   ├── platform-admin/          # Your internal operations console
│   ├── api/                     # NestJS application
│   └── workers/                 # Jobs, automation and integrations
├── packages/
│   ├── ui/                      # Shared UI components
│   ├── themes/                  # Design tokens and theme presets
│   ├── page-builder/            # Storefront block schemas/renderers
│   ├── database/                # Prisma schema and migrations
│   ├── auth/                    # Authentication and authorization
│   ├── commerce/                # Cart, pricing, inventory and orders
│   ├── automation/              # Rules, triggers and actions
│   ├── integrations/
│   │   ├── instagram/
│   │   ├── whatsapp/
│   │   ├── razorpay/
│   │   ├── stripe/
│   │   ├── shipping/
│   │   └── email/
│   ├── analytics/               # Event contracts and calculations
│   ├── seo/                     # Metadata, schema and sitemap helpers
│   ├── validation/              # Shared validation schemas
│   └── config/                  # ESLint, TypeScript and environment config
├── infrastructure/
│   ├── terraform/
│   ├── docker/
│   └── monitoring/
├── tests/
│   ├── e2e/
│   ├── integration/
│   └── performance/
└── docs/
    ├── architecture/
    ├── api/
    ├── runbooks/
    └── compliance/
```

---

# 7. Core data model

| Entity | Important relationships |
| --- | --- |
| Tenant | Plans, domains, users, stores and integrations |
| Store | Theme, pages, catalog, payment and shipping settings |
| Product | Variants, media, collections, inventory and SEO |
| Customer | Addresses, consent, orders, identities and conversations |
| SocialIdentity | Customer plus Instagram/WhatsApp channel identity |
| Conversation | Channel, participants, messages, lead and attribution |
| Cart/Checkout | Customer, items, discounts and attribution |
| Order | Payments, fulfillments, refunds and customer |
| Lead | Customer, stage, source, campaign and assigned agent |
| AutomationRule | Trigger, conditions, actions, status and execution limits |
| Event | Tenant, actor, type, payload and timestamp |
| MetricDaily | Tenant, date, channel, product and calculated values |

Use UUIDs, store money as integer minor units, keep timestamps in UTC and retain immutable snapshots of product name, tax and price inside order items.

---

# 8. Key workflows

## New influencer onboarding

The platform creates a tenant, assigns a plan, collects merchant and tax information, connects the payment provider, connects social accounts, selects a theme, imports products, configures shipping and legal pages, previews the storefront and publishes the custom domain.

## Website purchase

The domain resolves the tenant, the server renders the tenant’s theme and catalog, the customer adds products, checkout calculates price and inventory, the payment provider confirms payment through a signed webhook, and the platform creates the order and starts fulfillment.

Never trust the browser redirect as proof of payment. The signed payment webhook is authoritative.

## Instagram comment to sale

A customer comments “price”, Meta sends a webhook, the system validates and deduplicates it, an automation rule matches the keyword, and an allowed private reply is sent with a tracked product or checkout link. The resulting order retains the conversation, campaign and social-source attribution.

## WhatsApp order

A user starts a conversation, the automation presents products through messages, catalog commerce or a WhatsApp Flow, the user chooses products and address details, and the platform creates a checkout. Payment happens through supported in-chat payments where available or a secure hosted checkout link.

Do not collect card details in DMs. Ever.

---

# 9. Security and compliance

Pregnancy and baby products make trust non-negotiable. Require accurate ingredients/materials, age suitability, warnings, manufacturer details, return policy and evidence for medical or health claims.

The platform should include encryption in transit and at rest, secret management, MFA, tenant RBAC, audit logs, signed webhook verification, idempotency keys, API rate limiting, bot protection, backups, disaster recovery and regular dependency scanning.

For India, have counsel validate DPDP obligations, Consumer Protection E-Commerce Rules, GST/invoicing, Legal Metrology labelling and product-specific requirements such as BIS, cosmetics or food rules. Also provide explicit marketing consent, consent withdrawal, retention policies, export/delete workflows and a clear split of responsibilities between your platform and each influencer.

---

# 10. Delivery roadmap

| Phase | Duration | Output |
| --- | --- | --- |
| Discovery and UX | 2 weeks | Requirements, user journeys, schemas and prototypes |
| Platform foundation | 3 weeks | Tenant system, authentication, RBAC, domains and CI/CD |
| Commerce MVP | 5 weeks | Catalog, inventory, storefront, cart, checkout, orders and payments |
| Theme system and SEO | 3 weeks | Page blocks, themes, metadata, structured data and sitemaps |
| Automation | 4 weeks | Instagram/WhatsApp onboarding, webhooks, rules and tracked checkout links |
| CRM and analytics | 4 weeks | Leads, unified timeline, attribution, funnel and sales dashboards |
| Hardening and pilot | 3 weeks | Security, performance, compliance checks and pilot onboarding |

A realistic first full version is roughly **20 to 24 weeks** with 2 frontend engineers, 2 backend engineers, 1 designer, 1 QA engineer and a product/technical lead. A narrower Store-plan MVP can ship in 10 to 12 weeks.

---

# 11. MVP boundary

Ship the first version with one country, one currency, one payment provider, one shipping integration, 3 to 5 theme presets, guest checkout, basic discounts, Instagram keyword automation and a simple sales dashboard.

Defer visual drag-and-drop editing, AI-generated replies, loyalty points, subscriptions, multi-currency, mobile apps, advanced warehouse management and microservices. Those are expensive distractions until influencers are consistently generating orders.

My strongest recommendation: **prove the Store plan with three pilot influencers before building the full CRM**. Instrument every interaction from day one, then build CRM screens over real behavior instead of guessing what influencers want.