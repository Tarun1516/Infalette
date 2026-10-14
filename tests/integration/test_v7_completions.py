"""Regression tests for the v7 completion pass.

Covers the seven gaps closed after the v6 audit:
1. Web UTM/campaign attribution end-to-end (checkout -> events -> lead)
2. Immutable tax snapshot on order items + invoice usage
3. COD settlement on delivery (payment PENDING -> SUCCEEDED)
4. MFA enforcement for admin roles (enrollment-scoped tokens)
5. Public guest order tracking endpoint
6. Product CSV import (upsert by SKU, quota-aware)
7. Live carrier shipping rates with per-tenant credentials + fallback
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/infalette-v7-tests.db")
os.environ.setdefault("RATE_LIMIT_FAIL_CLOSED", "false")

from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _make_tenant(session, name="V7T"):
    from infalette_database.models.tenant import Tenant

    tenant = Tenant(name=name, slug=f"{name.lower()}-{uuid4().hex[:6]}", plan="store")
    session.add(tenant)
    await session.flush()
    return tenant


async def _make_product(session, tenant_id, price_cents=10000, tax_class="standard"):
    from infalette_database.models.product import Product, ProductStatus

    product = Product(
        tenant_id=tenant_id,
        name=f"Bottle {uuid4().hex[:6]}",
        slug=f"bottle-{uuid4().hex[:6]}",
        sku=f"V7-{uuid4().hex[:6]}",
        price_cents=price_cents,
        inventory_quantity=10,
        tax_class=tax_class,
        status=ProductStatus.ACTIVE,
    )
    session.add(product)
    await session.flush()
    return product


async def _make_cart_with_item(session, tenant_id, product, qty=1):
    from infalette_database.models.cart import Cart
    from infalette_database.models.cart_item import CartItem

    cart = Cart(tenant_id=tenant_id, session_key=f"v7-{uuid4().hex[:8]}")
    session.add(cart)
    await session.flush()
    item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=qty,
        price_cents=product.price_cents,
    )
    session.add(item)
    await session.flush()
    return cart


# ---------------------------------------------------------------------------
# 1 + 2: UTM attribution and tax snapshot through checkout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_captures_utm_and_resolves_campaign(db_session):
    from infalette_validation.schemas import (
        CheckoutCreate,
        CustomerDataSchema,
        AddressSchema,
        AttributionSchema,
    )
    from infalette_commerce.checkout import CheckoutService
    from infalette_database.models.campaign import Campaign
    from infalette_database.models.event import Event
    from sqlalchemy import select

    tenant = await _make_tenant(db_session)
    campaign = Campaign(
        tenant_id=tenant.id,
        name="Summer Baby Sale",
        slug=f"summer-{uuid4().hex[:4]}",
        source="website",
        status="active",
    )
    db_session.add(campaign)
    await db_session.flush()

    product = await _make_product(db_session, tenant.id, price_cents=10000)
    cart = await _make_cart_with_item(db_session, tenant.id, product)

    data = CheckoutCreate(
        customer_data=CustomerDataSchema(email=f"v7-{uuid4().hex[:4]}@example.com"),
        shipping_address=AddressSchema(
            line1="1 MG Road", city="Bengaluru", state="Karnataka",
            postal_code="560001", country="India",
        ),
        billing_address=AddressSchema(
            line1="1 MG Road", city="Bengaluru", state="Karnataka",
            postal_code="560001", country="India",
        ),
        attribution=AttributionSchema(
            utm_source="instagram_bio",
            utm_medium="social",
            utm_campaign=campaign.slug,
        ),
    )

    checkout = await CheckoutService().create_checkout(
        tenant.id, None, data, db_session, session_key=cart.session_key
    )

    # Attribution stamped on the checkout row, campaign resolved by slug
    attr = checkout.attribution_json
    assert attr["utm_campaign"] == campaign.slug
    assert attr["source"] == "instagram_bio"
    assert attr.get("campaign_id") == str(campaign.id)

    # checkout.created event carries the attribution join keys
    event = (
        await db_session.execute(
            select(Event).where(
                Event.tenant_id == tenant.id,
                Event.event_type == "checkout.created",
            )
        )
    ).scalars().first()
    assert event is not None
    assert event.payload_json.get("utm_campaign") == campaign.slug
    assert event.payload_json.get("campaign_id") == str(campaign.id)


@pytest.mark.asyncio
async def test_tax_snapshot_flows_to_order_item_and_invoice(db_session):
    from infalette_validation.schemas import (
        CheckoutCreate,
        CustomerDataSchema,
        AddressSchema,
    )
    from infalette_commerce.checkout import CheckoutService
    from infalette_commerce.invoice import InvoiceService
    from infalette_database.models.payment import Payment, PaymentProvider, PaymentStatus
    from infalette_database.models.order_item import OrderItem
    from sqlalchemy import select

    tenant = await _make_tenant(db_session)
    product = await _make_product(db_session, tenant.id, price_cents=10000, tax_class="standard")
    cart = await _make_cart_with_item(db_session, tenant.id, product, qty=2)

    data = CheckoutCreate(
        customer_data=CustomerDataSchema(email=f"v7-{uuid4().hex[:4]}@example.com"),
        shipping_address=AddressSchema(
            line1="1 MG Road", city="Bengaluru", state="Karnataka",
            postal_code="560001", country="India",
        ),
        billing_address=AddressSchema(
            line1="1 MG Road", city="Bengaluru", state="Karnataka",
            postal_code="560001", country="India",
        ),
    )
    svc = CheckoutService()
    checkout = await svc.create_checkout(
        tenant.id, None, data, db_session, session_key=cart.session_key
    )

    # Snapshot exists on checkout items (20000 * 18% = 3600)
    item_json = checkout.items_json[0]
    assert item_json["tax_cents"] == 3600
    assert item_json["product_snapshot"]["tax_cents"] == 3600
    assert item_json["product_snapshot"]["tax_rate_bps"] == 1800

    # Confirm checkout -> order item carries the immutable snapshot
    payment = Payment(
        tenant_id=tenant.id,
        provider=PaymentProvider.RAZORPAY,
        provider_payment_id=f"pay_{uuid4().hex[:8]}",
        amount_cents=checkout.total_cents,
        currency=checkout.currency,
        status=PaymentStatus.SUCCEEDED,
    )
    db_session.add(payment)
    await db_session.flush()
    order = await svc._confirm_checkout(checkout.id, payment, db_session)

    order_item = (
        await db_session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    ).scalars().first()
    assert order_item is not None
    assert order_item.tax_cents == 3600
    assert order_item.tax_rate_bps == 1800

    # Invoice uses the snapshot (not a recomputation)
    invoice = await InvoiceService().generate_invoice(order.id, db_session)
    line = invoice["line_items"][0] if isinstance(invoice.get("line_items"), list) else None
    assert line is not None
    assert line["tax_cents"] == 3600


# ---------------------------------------------------------------------------
# 3: COD settlement on delivery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cod_payment_settles_on_delivery(db_session):
    from infalette_commerce.orders import OrderService
    from infalette_database.models.order import Order, OrderStatus
    from infalette_database.models.payment import Payment, PaymentProvider, PaymentStatus
    from infalette_database.models.event import Event
    from sqlalchemy import select

    tenant = await _make_tenant(db_session)
    order = Order(
        tenant_id=tenant.id,
        status=OrderStatus.CONFIRMED,
        total_cents=500000,
        currency="INR",
    )
    db_session.add(order)
    await db_session.flush()
    payment = Payment(
        tenant_id=tenant.id,
        order_id=order.id,
        provider=PaymentProvider.COD,
        provider_payment_id=f"cod_{uuid4().hex[:8]}",
        amount_cents=500000,
        currency="INR",
        status=PaymentStatus.PENDING,
    )
    db_session.add(payment)
    await db_session.commit()

    svc = OrderService()
    await svc.update_order_status(tenant.id, order.id, OrderStatus.PROCESSING, db_session)
    await svc.update_order_status(tenant.id, order.id, OrderStatus.SHIPPED, db_session)
    await svc.update_order_status(tenant.id, order.id, OrderStatus.DELIVERED, db_session)

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.SUCCEEDED

    event = (
        await db_session.execute(
            select(Event).where(
                Event.tenant_id == tenant.id,
                Event.event_type == "payment.succeeded",
            )
        )
    ).scalars().first()
    assert event is not None
    assert event.payload_json.get("settled_on_delivery") is True


# ---------------------------------------------------------------------------
# 4: MFA enforcement for admins
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_without_mfa_gets_enrollment_scoped_token(db_session):
    from infalette_auth.schemas import LoginRequest
    from infalette_auth.jwt import TokenManager
    from infalette_auth.security import PasswordHasher
    from apps.api.modules.auth.services import (
        login,
        setup_mfa,
        confirm_mfa_enrollment,
    )
    from infalette_database.models.user import User

    hasher = PasswordHasher()
    user = User(
        tenant_id=None,
        email=f"owner-{uuid4().hex[:6]}@example.com",
        password_hash=hasher.hash_password("super-secret-pw"),
        first_name="Tenant", last_name="Owner",
        role="tenant_owner",
    )
    db_session.add(user)
    await db_session.commit()

    # 1) Login without MFA enrollment -> restricted enrollment token
    response = await login(
        LoginRequest(email=user.email, password="super-secret-pw"), db_session
    )
    assert response.mfa_required is True
    assert response.scope == "mfa_enrollment"

    payload = TokenManager().decode_token(response.access_token)
    assert payload.scope == "mfa_enrollment"

    # 2) Enroll: setup generates the secret, confirm with a valid TOTP code
    setup = await setup_mfa(user, db_session)
    assert setup.secret

    import pyotp

    code = pyotp.TOTP(setup.secret).now()
    full = await confirm_mfa_enrollment(user, code, db_session)
    assert user.mfa_enabled is True
    assert full.refresh_token  # real refresh token issued now

    full_payload = TokenManager().decode_token(full.access_token)
    assert full_payload.scope is None

    # 3) Subsequent logins require (and accept) the TOTP code
    with pytest.raises(ValueError, match="MFA code required"):
        await login(
            LoginRequest(email=user.email, password="super-secret-pw"), db_session
        )

    ok = await login(
        LoginRequest(
            email=user.email,
            password="super-secret-pw",
            mfa_code=pyotp.TOTP(setup.secret).now(),
        ),
        db_session,
    )
    assert ok.mfa_required is False


# ---------------------------------------------------------------------------
# 5: Public guest order tracking
# ---------------------------------------------------------------------------

def _run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_public_track_order_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from infalette_database.base import Base
    from infalette_database.session import get_async_session
    from apps.api.modules.public.routes import router as public_router
    from infalette_database.models.tenant import Tenant
    from infalette_database.models.customer import Customer
    from infalette_database.models.order import Order, OrderStatus
    from infalette_database.models.fulfillment import Fulfillment

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with maker() as session:
            tenant = Tenant(name="TrackT", slug=f"track-{uuid4().hex[:6]}", plan="store")
            session.add(tenant)
            await session.flush()
            customer = Customer(
                tenant_id=tenant.id,
                email="shopper@example.com",
                first_name="S", last_name="H",
            )
            session.add(customer)
            await session.flush()
            order = Order(
                tenant_id=tenant.id,
                customer_id=customer.id,
                status=OrderStatus.SHIPPED,
                total_cents=123400,
                currency="INR",
            )
            session.add(order)
            await session.flush()
            session.add(
                Fulfillment(
                    order_id=order.id,
                    tracking_number="TRK123456",
                    carrier="Delhivery",
                )
            )
            await session.commit()
            return tenant.slug, order.id

    slug, order_id = _run(_seed())

    app = FastAPI()
    app.include_router(public_router, prefix="/api/v1/public")

    async def _get():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_async_session] = _get
    client = TestClient(app)

    # Correct email -> tracking details (case-insensitive match)
    r = client.get(
        f"/api/v1/public/track-order?order_id={order_id}&email=Shopper@example.com",
        headers={"X-Tenant": slug},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "shipped"
    assert body["tracking"][0]["tracking_number"] == "TRK123456"
    assert body["tracking"][0]["carrier"] == "Delhivery"
    assert "shipped" in body["timeline"] and "delivered" not in body["timeline"]

    # Wrong email -> 404 (existence not revealed)
    r2 = client.get(
        f"/api/v1/public/track-order?order_id={order_id}&email=attacker@example.com",
        headers={"X-Tenant": slug},
    )
    assert r2.status_code == 404


# ---------------------------------------------------------------------------
# 6: Product CSV import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_product_csv_import_creates_then_updates(db_session):
    from apps.api.modules.product.services import import_products_csv
    from infalette_database.models.product import Product
    from sqlalchemy import select

    tenant = await _make_tenant(db_session)

    csv_text = (
        "name,sku,price,inventory,tax_class,ingredients,safety_info,age_suitability\n"
        f"Baby Lotion,{uuid4().hex[:8]},499,25,standard,\"aloe, shea\",\"External use only\",newborn\n"
        f"Bibs Pack,{uuid4().hex[:8]},299.50,10,reduced,,,\n"
        ",,100,1,,,,\n"  # invalid: missing name+sku
    )
    result = await import_products_csv(tenant.id, csv_text, db_session)
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["skipped"] == 1
    assert len(result["errors"]) == 1

    rows = (
        await db_session.execute(select(Product).where(Product.tenant_id == tenant.id))
    ).scalars().all()
    assert len(rows) == 2
    target = [r for r in rows if r.name == "Baby Lotion"][0]
    assert target.price_cents == 49900  # rupees -> cents
    assert target.safety_info == "External use only"

    # Second import with same SKU updates (499 -> 599)
    update_csv = (
        "name,sku,price_cents,inventory\n"
        f"Baby Lotion,{target.sku},599,50\n"
    )
    result2 = await import_products_csv(tenant.id, update_csv, db_session)
    assert result2["created"] == 0
    assert result2["updated"] == 1

    await db_session.refresh(target)
    assert target.price_cents == 599
    assert target.inventory == 50


# ---------------------------------------------------------------------------
# 7: Live carrier shipping rates (per-tenant credentials) with fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_carrier_rate_used_when_configured(monkeypatch):
    from infalette_commerce.shipping import ShippingService
    from infalette_integrations.shipping.client import ShippingProviderClient

    rules = {
        "rates": {"standard": {"price_cents": 10000}},
        "carrier": {
            "provider": "delhivery",
            "api_key": "tenant-key",
            "origin_pincode": "560001",
        },
    }

    async def _fake_rates(self, provider, origin_pin, destination_pin, weight_kg, **kwargs):
        assert provider == "delhivery"
        assert kwargs.get("api_key") == "tenant-key"
        return [
            {"total_cents": 9500, "carrier": "Delhivery", "estimated_days": 2},
            {"total_cents": 7250, "carrier": "Delhivery Surface", "estimated_days": 4},
        ]

    monkeypatch.setattr(ShippingProviderClient, "get_shipping_options", _fake_rates)

    svc = ShippingService(rules=rules)
    result = await svc.get_shipping_cost(
        zone="MH", weight_kg=1.0, order_total_cents=50000,
        destination_pincode="400001",
    )
    assert result["live"] is True
    assert result["price_cents"] == 7250  # cheapest live rate wins


@pytest.mark.asyncio
async def test_live_carrier_failure_falls_back_to_zone_rules(monkeypatch):
    from infalette_commerce.shipping import ShippingService
    from infalette_integrations.shipping.client import ShippingProviderClient

    rules = {
        "rates": {"standard": {"price_cents": 10000}},
        "carrier": {"provider": "delhivery", "api_key": "bad-key", "origin_pincode": "560001"},
    }

    async def _boom(self, *args, **kwargs):
        raise RuntimeError("carrier unreachable")

    monkeypatch.setattr(ShippingProviderClient, "get_shipping_options", _boom)

    svc = ShippingService(rules=rules)
    result = await svc.get_shipping_cost(
        zone="MH", weight_kg=1.0, order_total_cents=50000,
        destination_pincode="400001",
    )
    assert result["live"] is False
    assert result["price_cents"] == 10000  # configured zone rate

    # No carrier config at all -> straight to zone rules
    plain = ShippingService(rules={"rates": {"standard": {"price_cents": 10000}}})
    result2 = await plain.get_shipping_cost(
        zone="MH", weight_kg=1.0, order_total_cents=50000,
        destination_pincode="400001",
    )
    assert result2["live"] is False
    assert result2["price_cents"] == 10000
