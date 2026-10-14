"""Regression tests for v6 audit fixes (docs/FINDINGS_REPORT_V6.md).

Each test exercises a chain that was broken before this fix pass:
public catalog access, address aliases, webhook replay idempotency,
store settings round-trip, automation rule creation, lead stage/import.
"""

from __future__ import annotations

import os

# Isolated DB for this module (must be set before app imports)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/infalette-v6-tests.db")
os.environ.setdefault("RATE_LIMIT_FAIL_CLOSED", "false")

from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# C1: anonymous storefront can read the public catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_endpoints_serve_anonymous_catalog():
    """Storefront fetches /public/* with only X-Tenant and gets real data."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from infalette_database.base import Base
    from infalette_database.session import get_async_session
    from apps.api.modules.public.routes import router as public_router
    from infalette_database.models.tenant import Tenant
    from infalette_database.models.store import Store
    from infalette_database.models.product import Product, ProductStatus

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        t = Tenant(name="Pub T", slug=f"pub-{uuid4().hex[:8]}", plan="store")
        session.add(t)
        await session.flush()
        s = Store(tenant_id=t.id, name="Pub Store", slug=f"ps-{uuid4().hex[:6]}")
        session.add(s)
        p = Product(
            tenant_id=t.id,
            name="Public Bottle",
            slug=f"public-bottle-{uuid4().hex[:6]}",
            sku=f"PUB-{uuid4().hex[:6]}",
            price_cents=99900,
            inventory_quantity=10,
            status=ProductStatus.ACTIVE,
        )
        session.add(p)
        await session.commit()
        slug, product_id = t.slug, p.id

    app = FastAPI()
    app.include_router(public_router, prefix="/api/v1/public")

    app.dependency_overrides[get_async_session] = _override(maker)

    try:
        client = TestClient(app)
        r = client.get("/api/v1/public/products", headers={"X-Tenant": slug})
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1

        r2 = client.get(f"/api/v1/public/products/{product_id}", headers={"X-Tenant": slug})
        assert r2.status_code == 200
        assert r2.json()["name"] == "Public Bottle"

        r3 = client.get("/api/v1/public/store", headers={"X-Tenant": slug})
        assert r3.status_code == 200

        r4 = client.get("/api/v1/public/pages", headers={"X-Tenant": slug})
        assert r4.status_code == 200

        # No tenant -> explicit 401 (not a crash)
        r5 = client.get("/api/v1/public/products")
        assert r5.status_code == 401
    finally:
        await engine.dispose()


def _override(maker):
    """Yield a session per request from the shared engine."""
    async def _get():
        async with maker() as s:
            yield s
    return _get


# ---------------------------------------------------------------------------
# C2: storefront-shaped addresses validate (address/pincode aliases)
# ---------------------------------------------------------------------------

def test_address_schema_accepts_storefront_aliases():
    from infalette_validation.schemas import AddressSchema

    a = AddressSchema(**{
        "address": "12 MG Road", "city": "Bengaluru", "state": "KA",
        "country": "IN", "pincode": "560001",
    })
    assert a.line1 == "12 MG Road"
    assert a.postal_code == "560001"

    b = AddressSchema(line1="x", city="y", state="z", country="IN", postal_code="1")
    assert b.line1 == "x"


def test_checkout_create_accepts_ui_payload():
    from infalette_validation.schemas import CheckoutCreate

    payload = {
        "customer_data": {"email": "g@example.com", "phone": "9876543210"},
        "shipping_address": {"address": "a", "city": "b", "state": "c", "country": "IN", "pincode": "1"},
        "billing_address": {"address": "a", "city": "b", "state": "c", "country": "IN", "pincode": "1"},
        "discount_codes": [],
    }
    data = CheckoutCreate(**payload)
    assert data.shipping_address.postal_code == "1"


# ---------------------------------------------------------------------------
# C5: store settings round-trip (columns now mapped on ORM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_settings_roundtrip(db_session):
    from apps.api.modules.store.services import update_store_settings, get_store_settings
    from infalette_database.models.store import Store
    from infalette_database.models.tenant import Tenant

    tenant = Tenant(name="ST", slug=f"st-{uuid4().hex[:6]}", plan="store")
    db_session.add(tenant)
    await db_session.flush()
    store = Store(tenant_id=tenant.id, name="S", slug=f"s-{uuid4().hex[:6]}")
    db_session.add(store)
    await db_session.flush()

    updated = await update_store_settings(
        tenant.id,
        {
            "name": "Renamed",
            "custom_domain": "shop.example.com",
            "logo_url": "https://cdn.example.com/logo.png",
            "currency": "USD",
            "tax_rate": 5,
            "theme_config": {"primary_color": "#ff0000"},
        },
        db_session,
    )
    assert updated["custom_domain"] == "shop.example.com"
    assert updated["currency"] == "USD"
    assert updated["tax_rate"] == 5
    assert updated["theme_config"]["primary_color"] == "#ff0000"


# ---------------------------------------------------------------------------
# C7: automation rule with conditions creates successfully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_automation_rule_with_conditions(db_session):
    from apps.api.modules.automation.services import create_automation_rule
    from infalette_database.models.tenant import Tenant

    tenant = Tenant(name="AT", slug=f"at-{uuid4().hex[:6]}", plan="store_automation")
    db_session.add(tenant)
    await db_session.flush()

    rule = await create_automation_rule(
        tenant.id,
        {
            "name": "Buy keyword",
            "trigger_type": "comment_keyword",
            "trigger_config": {},
            "conditions": [{"field": "text", "operator": "contains", "value": "buy"}],
            "actions": [
                {"action_type": "send_notification", "config": {}, "order": 0}
            ],
        },
        db_session,
    )
    assert rule.conditions_json["conditions"][0]["value"] == "buy"
    assert rule.trigger_type.value == "comment_keyword"


# ---------------------------------------------------------------------------
# M9/M11/M12/C9: route registrations the frontend depends on
# ---------------------------------------------------------------------------

def _route_set():
    from apps.api.main import create_app

    app = create_app()
    found = set()
    for r in app.routes:
        if hasattr(r, "original_router"):
            prefix = getattr(r.include_context, "prefix", "") or ""
            for sr in r.original_router.routes:
                found.add(
                    (
                        f"{prefix}{getattr(sr, 'path', '')}",
                        tuple(sorted(getattr(sr, "methods", []) or [])),
                    )
                )
        else:
            found.add(
                (
                    getattr(r, "path", ""),
                    tuple(sorted(getattr(r, "methods", []) or [])),
                )
            )
    return found


def test_refund_order_route_registered():
    found = _route_set()
    assert ("/api/v1/orders/{order_id}/refunds", ("POST",)) in found


def test_lead_stage_and_import_routes_registered():
    found = _route_set()
    assert ("/api/v1/leads/{lead_id}/stage", ("PATCH",)) in found
    assert ("/api/v1/leads/import", ("POST",)) in found


def test_platform_billing_routes_registered():
    paths = {p for p, _ in _route_set()}
    for expected in (
        "/api/v1/platform/plans",
        "/api/v1/platform/subscriptions",
        "/api/v1/tenants/onboard",
    ):
        assert expected in paths, f"{expected} missing"


def test_csv_import_parses_rows():
    from apps.api.modules.lead.routes import _parse_csv

    rows = _parse_csv("email,first_name\na@b.com,A\nc@d.com,C\n")
    assert len(rows) == 2
    assert rows[0]["email"] == "a@b.com"


# ---------------------------------------------------------------------------
# C4: duplicate webhook replay does not create a second order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_checkout_is_idempotent(db_session):
    from infalette_commerce.checkout import CheckoutService
    from infalette_database.models.checkout import Checkout, CheckoutStatus
    from infalette_database.models.order import Order
    from infalette_database.models.payment import Payment, PaymentProvider, PaymentStatus
    from infalette_database.models.tenant import Tenant
    from sqlalchemy import select as _select

    tenant = Tenant(name="IT", slug=f"it-{uuid4().hex[:6]}", plan="store")
    db_session.add(tenant)
    await db_session.flush()

    checkout = Checkout(
        tenant_id=tenant.id,
        cart_id=uuid4(),  # NOT NULL in schema; not exercised by this test
        status=CheckoutStatus.PENDING,
        total_cents=11800,
        currency="INR",
    )
    db_session.add(checkout)
    await db_session.flush()

    payment = Payment(
        tenant_id=tenant.id,
        provider=PaymentProvider.RAZORPAY,
        amount_cents=11800,
        currency="INR",
        status=PaymentStatus.SUCCEEDED,
        provider_payment_id="pay_test_1",
    )
    db_session.add(payment)
    await db_session.flush()

    service = CheckoutService.__new__(CheckoutService)

    order1 = await service._confirm_checkout(checkout.id, payment, db_session)
    order2 = await service._confirm_checkout(checkout.id, payment, db_session)

    assert order1.id == order2.id, "replayed confirmation must return the same order"

    count = len((
        await db_session.execute(_select(Order).where(Order.checkout_id == checkout.id))
    ).scalars().all())
    assert count == 1, f"expected exactly 1 order, found {count}"
