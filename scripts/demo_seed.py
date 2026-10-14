"""Demo seed script — creates plans, a demo tenant, owner user, theme,
homepage blocks and sample products. Idempotent: safe to re-run.

Usage:
    python scripts/demo_seed.py                 # uses DATABASE_URL (sqlite fallback)
Env:
    DEMO_TENANT_SLUG   (default: demo-store)
    DEMO_OWNER_EMAIL   (default: owner@demo.test)
    DEMO_OWNER_PASSWORD(default: demo1234)
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
for pkg in ["config", "validation", "database", "auth", "commerce",
            "automation", "analytics", "seo", "integrations"]:
    sys.path.insert(0, str(REPO / "packages" / pkg / "src"))

TENANT_SLUG = os.environ.get("DEMO_TENANT_SLUG", "demo-store")
OWNER_EMAIL = os.environ.get("DEMO_OWNER_EMAIL", "owner@demo.test")
OWNER_PASSWORD = os.environ.get("DEMO_OWNER_PASSWORD", "demo1234")

PLANS = [
    {"name": "Store", "slug": "store", "price_cents": 99900,
     "description": "Custom storefront, catalog, checkout, orders, SEO"},
    {"name": "Store + Automation", "slug": "store_automation", "price_cents": 249900,
     "description": "Adds Instagram/WhatsApp automation, checkout links, unified inbox"},
    {"name": "Store + Automation + CRM", "slug": "store_automation_crm", "price_cents": 499900,
     "description": "Adds full CRM, funnel analytics, segments, exports"},
]

PRODUCTS = [
    dict(name="Organic Baby Lotion", slug="organic-baby-lotion", sku="DEMO-LOTION",
         price_cents=49900, tax_class="standard", inventory_quantity=120,
         description="Fragrance-free moisturizer for sensitive newborn skin.",
         ingredients="Aloe vera, shea butter, calendula",
         safety_info="External use only. Patch test recommended.",
         age_suitability="newborn",
         image="https://images.unsplash.com/photo-1583846783214-7229a91b20ed?w=800&h=800&fit=crop&q=80"),
    dict(name="Postpartum Recovery Tea", slug="postpartum-recovery-tea", sku="DEMO-TEA",
         price_cents=34900, sale_price_cents=29900, tax_class="reduced",
         inventory_quantity=80,
         description="Caffeine-free herbal blend supporting postpartum recovery.",
         ingredients="Fennel, fenugreek, chamomile",
         safety_info="Consult a physician if nursing with medical conditions.",
         age_suitability="all",
         image="https://images.unsplash.com/photo-1597318181409-cf64d0b5d8a2?w=800&h=800&fit=crop&q=80"),
    dict(name="Muslin Swaddle Wrap (3-pack)", slug="muslin-swaddle-3pack", sku="DEMO-SWADDLE",
         price_cents=59900, tax_class="standard", inventory_quantity=200,
         description="100% organic cotton, breathable 4-layer muslin.",
         ingredients="100% GOTS-certified organic cotton",
         safety_info="Keep away from fire.",
         age_suitability="newborn",
         image="https://images.unsplash.com/photo-1522771930-78848d9293e8?w=800&h=800&fit=crop&q=80"),
    dict(name="Silicone Feeding Set", slug="silicone-feeding-set", sku="DEMO-FEED",
         price_cents=79900, tax_class="standard", inventory_quantity=60,
         description="Food-grade suction bowl, spoon and cup for self-feeding.",
         ingredients="BPA-free food-grade silicone",
         safety_info="Inspect before each use; discard if damaged.",
         age_suitability="infant",
         image="https://images.unsplash.com/photo-1607619056574-7b8d3ee536b2?w=800&h=800&fit=crop&q=80"),
    dict(name="Pregnancy Body Pillow", slug="pregnancy-body-pillow", sku="DEMO-PILLOW",
         price_cents=149900, sale_price_cents=129900, tax_class="standard",
         inventory_quantity=35,
         description="Full-length U-shaped support pillow for second/third trimester.",
         ingredients="Polyester fill, cotton-poly cover",
         safety_info="Not a medical device.",
         pregnancy_stage="pregnancy_second_trimester",
         image="https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800&h=800&fit=crop&q=80"),
    dict(name="Toddler Bath Toy Set", slug="toddler-bath-toy-set", sku="DEMO-BATH",
         price_cents=24900, tax_class="standard", inventory_quantity=150,
         description="Mold-free sealed bath toys, 12m+.",
         ingredients="Sealed ABS plastic, natural rubber",
         safety_info="Adult supervision required around water.",
         age_suitability="toddler",
         image="https://images.unsplash.com/photo-1558877385-81a1c7e67d72?w=800&h=800&fit=crop&q=80"),
]

HOME_BLOCKS = [
    {"type": "hero", "data": {
        "eyebrow": "Curated by @demomama",
        "title": "Everything for the fourth trimester",
        "subtitle": "Handpicked pregnancy, postpartum & baby essentials — tried on real babies.",
        "cta_label": "Shop the edit", "cta_url": "/demo-store/products"}},
    {"type": "featured_products", "data": {"title": "Bestsellers", "limit": 4}},
    {"type": "testimonials", "data": {"items": [
        {"quote": "The recovery tea got me through week two.", "author": "Priya, Bengaluru"},
        {"quote": "Fast delivery and beautiful packaging.", "author": "Sara, Mumbai"}]}},
    {"type": "faq", "data": {"items": [
        {"q": "Do you ship pan-India?", "a": "Yes — free above ₹1,000."},
        {"q": "Are products BIS certified?", "a": "Where applicable, certifications are listed on each product page."}]}},
    {"type": "instagram_gallery", "data": {"title": "@demomama on Instagram"}},
]


async def main() -> None:
    from sqlalchemy import select

    from infalette_auth.security import PasswordHasher
    from infalette_database.base import Base
    from infalette_database.models.discount_code import DiscountCode
    from infalette_database.models.page import Page
    from infalette_database.models.plan import Plan, PlanType
    from infalette_database.models.product import (
        Product, ProductAgeSuitability, ProductPregnancyStage,
    )
    from infalette_database.models.store import Store
    from infalette_database.models.tenant import Tenant
    from infalette_database.models.user import User
    from infalette_database.session import get_engine, get_session_factory

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    created = []
    async with get_session_factory()() as s:
        # Plans
        plan_by_slug = {}
        for p in PLANS:
            row = (await s.execute(select(Plan).where(Plan.slug == p["slug"]))).scalar_one_or_none()
            if not row:
                row = Plan(
                name=p["name"], slug=p["slug"], plan_type=PlanType(p["slug"]),
                price_cents=p["price_cents"], currency="INR",
                interval="month", features_json={"description": p["description"]},
            )
                s.add(row)
                await s.flush()
                created.append(f"plan:{p['slug']}")
            plan_by_slug[p["slug"]] = row

        # Tenant
        tenant = (await s.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(name="Infalette", slug=TENANT_SLUG, plan="store_automation",
                            status="active")
            s.add(tenant)
            await s.flush()
            created.append(f"tenant:{TENANT_SLUG}")
        if not tenant.plan_id:
            tenant.plan_id = plan_by_slug["store_automation"].id

        # Owner user
        user = (await s.execute(select(User).where(User.email == OWNER_EMAIL))).scalar_one_or_none()
        if not user:
            user = User(
                tenant_id=tenant.id, email=OWNER_EMAIL,
                password_hash=PasswordHasher().hash_password(OWNER_PASSWORD),
                first_name="Infalette", last_name="Owner",
                role="tenant_owner", status="active",
            )
            s.add(user)
            await s.flush()
            created.append(f"user:{OWNER_EMAIL}")

        # Store
        store = (await s.execute(select(Store).where(Store.tenant_id == tenant.id))).scalar_one_or_none()
        if not store:
            from datetime import datetime, timezone as _tz

            store = Store(tenant_id=tenant.id, name="Infalette",
                          slug=f"{TENANT_SLUG}-main",
                          description="Curated pregnancy, postpartum, baby & childcare essentials.",
                          status="published",
                          published_at=datetime.now(_tz.utc))
            s.add(store)
            await s.flush()
            created.append("store")

        # Primary domain (Domain model owns DNS records)
        from infalette_database.models.domain import Domain

        dom = (await s.execute(select(Domain).where(
            Domain.tenant_id == tenant.id,
            Domain.domain == f"{TENANT_SLUG}.infalette.com"))).scalar_one_or_none()
        if not dom:
            s.add(Domain(tenant_id=tenant.id,
                         domain=f"{TENANT_SLUG}.infalette.com",
                         is_primary=True, verified=True))
            created.append(f"domain:{TENANT_SLUG}.infalette.com")

        # Products
        for pdata in PRODUCTS:
            exists = (await s.execute(select(Product).where(
                Product.tenant_id == tenant.id, Product.sku == pdata["sku"]))).scalar_one_or_none()
            age = pdata.get("age_suitability")
            stage = pdata.get("pregnancy_stage")
            image_url = pdata.get("image") or f"https://cdn.infalette.com/demo/{pdata['slug']}.jpg"
            if exists:
                # Backfill image_url on existing demo rows so the storefront
                # doesn't show broken placeholders after this seed change.
                if getattr(exists, "image_url", None) != image_url:
                    exists.image_url = image_url
                    exists.images_json = [image_url]
                    created.append(f"product-image:{pdata['sku']}")
                continue
            prod = Product(
                tenant_id=tenant.id,
                name=pdata["name"], slug=pdata["slug"], sku=pdata["sku"],
                description=pdata["description"], price_cents=pdata["price_cents"],
                sale_price_cents=pdata.get("sale_price_cents"),
                tax_class=pdata["tax_class"], inventory_quantity=pdata["inventory_quantity"],
                inventory_track=True, inventory_policy="deny",
                images_json=[image_url],
                image_url=image_url,
                ingredients=pdata.get("ingredients"), safety_info=pdata.get("safety_info"),
                age_suitability=ProductAgeSuitability(age) if age else None,
                pregnancy_stage=ProductPregnancyStage(stage) if stage else None,
                meta_title=pdata["name"], meta_description=pdata["description"],
                status="active",
            )
            s.add(prod)
            await s.flush()
            created.append(f"product:{pdata['sku']}")

        # Homepage page with blocks
        home = (await s.execute(select(Page).where(
            Page.tenant_id == tenant.id, Page.slug == "home"))).scalar_one_or_none()
        if not home:
            home = Page(
                tenant_id=tenant.id, store_id=store.id,
                title="Home", slug="home", path="/",
                blocks_json=HOME_BLOCKS, status="published", is_homepage=True,
                meta_title="Infalette — mother & baby essentials",
                meta_description="Pregnancy, postpartum, baby and childcare picks curated by @demomama",
            )
            s.add(home)
            created.append("page:home")

        # Welcome coupon
        coupon = (await s.execute(select(DiscountCode).where(
            DiscountCode.tenant_id == tenant.id, DiscountCode.code == "WELCOME10"))).scalar_one_or_none()
        if not coupon:
            s.add(DiscountCode(
                tenant_id=tenant.id, code="WELCOME10", discount_type="percentage",
                value=10, minimum_order_cents=50000, is_active=True,
                expires_at=datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1),
            ))
            created.append("coupon:WELCOME10")

        await s.commit()

    print("Seed complete.")
    print("  created :", ", ".join(created) if created else "(nothing new — already seeded)")
    print("  login   :", f"{OWNER_EMAIL} / {OWNER_PASSWORD}")
    print("  storefront:", f"/{TENANT_SLUG}")
    print("  admin   : http://localhost:3001 (login with credentials above)")


if __name__ == "__main__":
    asyncio.run(main())
