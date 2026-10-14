"""Regression tests for v6 Phase 2–4 fixes.

Covers: keyword gating, consent enforcement, checkout.unpaid emission,
expired-checkout inventory release, atomic inventory compensation,
public /track endpoint, dashboard contract, plan-tier gates, coupon
consumption on payment.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/infalette-v6p2.db")
os.environ.setdefault("RATE_LIMIT_FAIL_CLOSED", "false")

from datetime import datetime, timedelta
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# M1: comment_keyword rules only fire when a keyword matches the text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keyword_rule_ignores_non_matching_message(db_session):
    from infalette_automation.triggers import TriggerEngine
    from infalette_automation.schemas import TriggerEvent

    class FakeRule:
        tenant_id = "00000000-0000-0000-0000-000000000000"
        status = "active"
        trigger_type = "comment_keyword"
        name = "buy rule"
        trigger_config = {}
        conditions_json = {"keywords": ["buy"], "conditions": []}

    engine = TriggerEngine()

    async def fake_get_rules(event, session):
        return [FakeRule()]

    engine.get_matching_rules = fake_get_rules  # type: ignore

    # Evaluate matching logic directly via evaluate_trigger path:
    matched_buy = engine.evaluate_trigger(
        {"keywords": ["buy"]},
        TriggerEvent(
            event_type="conversation.message_received",
            tenant_id=FakeRule.tenant_id,
            actor_id=None,
            payload={"text": "how much to buy this?"},
            timestamp=datetime.utcnow(),
        ),
    )
    matched_no = engine.evaluate_trigger(
        {"keywords": ["buy"]},
        TriggerEvent(
            event_type="conversation.message_received",
            tenant_id=FakeRule.tenant_id,
            actor_id=None,
            payload={"text": "cute picture!"},
            timestamp=datetime.utcnow(),
        ),
    )
    assert matched_buy is True
    assert matched_no is False


# ---------------------------------------------------------------------------
# M17: consent gate blocks outbound without consent
# ---------------------------------------------------------------------------

def test_consent_gate():
    from infalette_commerce.consent import can_contact

    assert can_contact({"email": True}, "email") is True
    assert can_contact({"email": False}, "email") is False
    assert can_contact({}, "email") is False          # opt-in default
    assert can_contact(None, "whatsapp") is False
    assert can_contact({"email": True, "marketing": False}, "email") is False


@pytest.mark.asyncio
async def test_abandoned_worker_skips_unconsented(db_session):
    """recover path consults consent before sending."""
    import inspect

    from apps.workers.tasks import abandoned as mod

    src = inspect.getsource(mod.recover_abandoned_carts)
    assert "customer_can_contact" in src, "consent gate missing in recovery worker"


# ---------------------------------------------------------------------------
# M3: checkout.unpaid task emits events for stale pending checkouts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_unpaid_emits_events(db_session):
    from apps.workers.tasks.checkout_unpaid import emit_unpaid_checkout_events
    from infalette_database.models.checkout import Checkout, CheckoutStatus
    from infalette_database.models.event import Event
    from infalette_database.models.tenant import Tenant
    from sqlalchemy import select as _select

    tenant = Tenant(name="UT", slug=f"ut-{uuid4().hex[:6]}", plan="store")
    db_session.add(tenant)
    await db_session.flush()

    stale = Checkout(
        tenant_id=tenant.id,
        cart_id=uuid4(),
        status=CheckoutStatus.PENDING,
        total_cents=5000,
        currency="INR",
        created_at=datetime.utcnow() - timedelta(hours=3),
    )
    fresh = Checkout(
        tenant_id=tenant.id,
        cart_id=uuid4(),
        status=CheckoutStatus.PENDING,
        total_cents=7000,
        currency="INR",
        created_at=datetime.utcnow(),
    )
    db_session.add_all([stale, fresh])
    await db_session.commit()

    result = await emit_unpaid_checkout_events(
        db_session, tenant_id=tenant.id, interval_minutes=60
    )
    assert result["emitted"] == 1, f"expected 1 event for stale checkout, got {result}"

    # Second run must dedupe (24h window)
    result2 = await emit_unpaid_checkout_events(
        db_session, tenant_id=tenant.id, interval_minutes=60
    )
    assert result2["emitted"] == 0 and result2["skipped_duplicate"] == 1


# ---------------------------------------------------------------------------
# M22b: expired checkouts release reserved stock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_checkout_release_restocks(db_session):
    from apps.workers.tasks.checkout_expiry import release_expired_checkouts
    from infalette_database.models.checkout import Checkout, CheckoutStatus
    from infalette_database.models.product import Product, ProductStatus
    from infalette_database.models.tenant import Tenant
    from sqlalchemy import select as _select

    tenant = Tenant(name="ET", slug=f"et-{uuid4().hex[:6]}", plan="store")
    db_session.add(tenant)
    await db_session.flush()
    product = Product(
        tenant_id=tenant.id,
        name="Restock me",
        slug=f"restock-{uuid4().hex[:6]}",
        sku=f"RS-{uuid4().hex[:6]}",
        price_cents=10000,
        inventory_quantity=8,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(product)
    await db_session.flush()

    expired = Checkout(
        tenant_id=tenant.id,
        cart_id=uuid4(),
        status=CheckoutStatus.PENDING,
        total_cents=10000,
        currency="INR",
        expires_at=datetime.utcnow() - timedelta(minutes=5),
    )
    db_session.add(expired)
    await db_session.flush()

    from infalette_database.models.checkout_item import CheckoutItem

    item = CheckoutItem(
        checkout_id=expired.id,
        product_id=product.id,
        variant_id=None,
        quantity=3,
        price_cents=10000,
        product_snapshot_json={"name": product.name},
    )
    db_session.add(item)
    await db_session.commit()

    result = await release_expired_checkouts(db_session, tenant_id=tenant.id)
    assert result["released_checkouts"] == 1
    assert result["released_units"] == 3

    await db_session.refresh(product)
    assert int(product.inventory_quantity) == 11, "stock must be restocked after expiry"


# ---------------------------------------------------------------------------
# M21/M22: atomic reserve compensates on partial failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_atomic_reserve_compensates(db_session):
    from infalette_commerce.inventory import reserve_inventory_atomic
    from infalette_database.models.product import Product, ProductStatus
    from infalette_database.models.tenant import Tenant

    tenant = Tenant(name="AT2", slug=f"at2-{uuid4().hex[:6]}", plan="store")
    db_session.add(tenant)
    await db_session.flush()
    p1 = Product(
        tenant_id=tenant.id, name="A", slug=f"a-{uuid4().hex[:4]}", sku=f"A-{uuid4().hex[:4]}",
        price_cents=100, inventory_quantity=10, status=ProductStatus.ACTIVE,
    )
    p2 = Product(
        tenant_id=tenant.id, name="B", slug=f"b-{uuid4().hex[:4]}", sku=f"B-{uuid4().hex[:4]}",
        price_cents=100, inventory_quantity=1, status=ProductStatus.ACTIVE,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    ok = await reserve_inventory_atomic(
        [(p1.id, 5, None), (p2.id, 99, None)],  # second fails
        db_session,
    )
    assert ok is False
    await db_session.refresh(p1)
    await db_session.refresh(p2)
    assert int(p1.inventory_quantity) == 10, "first reservation must be compensated"
    assert int(p2.inventory_quantity) == 1


# ---------------------------------------------------------------------------
# Public /track endpoint accepts allow-listed funnel events (M6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_track_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from infalette_database.base import Base
    from infalette_database.session import get_async_session
    from apps.api.modules.public.routes import router as public_router
    from infalette_database.models.tenant import Tenant

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        t = Tenant(name="TT", slug=f"tt-{uuid4().hex[:6]}", plan="store")
        session.add(t)
        await session.commit()
        slug = t.slug

    async def _get():
        async with maker() as s:
            yield s

    app = FastAPI()
    app.include_router(public_router, prefix="/api/v1/public")
    app.dependency_overrides[get_async_session] = _get

    client = TestClient(app)
    r = client.post(
        "/api/v1/public/track",
        json={"event_type": "product.viewed", "product_id": str(uuid4())},
        headers={"X-Tenant": slug},
    )
    assert r.status_code == 202, r.text

    r2 = client.post(
        "/api/v1/public/track",
        json={"event_type": "admin.secrets"},
        headers={"X-Tenant": slug},
    )
    assert r2.status_code == 422, "non-allowlisted events must be rejected"

    await engine.dispose()


# ---------------------------------------------------------------------------
# Dashboard contract exposes the flat keys the admin tiles read (M5)
# ---------------------------------------------------------------------------

def test_dashboard_route_source_has_flat_keys():
    import inspect

    from apps.api.modules.analytics import routes

    src = inspect.getsource(routes.get_dashboard_metrics)
    for key in ("total_sales_cents", "net_sales_cents", "aov", "conversion_rate", "series"):
        assert key in src, f"dashboard route missing frontend key {key}"


# ---------------------------------------------------------------------------
# Plan tiers: social-funnel & attribution require CRM-tier flags (M26)
# ---------------------------------------------------------------------------

def test_tier_gates_wired():
    import inspect

    from apps.api.modules.analytics import routes
    from apps.api.modules.campaigns import routes as croutes
    from apps.api.core.feature_flags import Feature, has_feature, Plan

    src = inspect.getsource(routes)
    assert "FUNNEL_FULL" in inspect.getsource(routes.get_social_funnel) or \
        'require_feature(Feature.FUNNEL_FULL)' in src
    assert "ADVANCED_DASHBOARD" in inspect.getsource(routes.get_channel_attribution)
    cam_src = inspect.getsource(croutes)
    assert "ADVANCED_DASHBOARD" in cam_src

    # Tier math: Limited funnel for store_automation, Full for CRM
    assert has_feature(Plan.STORE_AUTOMATION, Feature.FUNNEL_ANALYTICS) is True
    assert has_feature(Plan.STORE_AUTOMATION, Feature.FUNNEL_FULL) is False
    assert has_feature(Plan.STORE_AUTOMATION_CRM, Feature.FUNNEL_FULL) is True
    assert has_feature(Plan.STORE_AUTOMATION_CRM, Feature.ADVANCED_DASHBOARD) is True
    assert has_feature(Plan.STORE_AUTOMATION, Feature.ADVANCED_DASHBOARD) is False
    assert has_feature(Plan.STORE, Feature.ADVANCED_DASHBOARD) is False


# ---------------------------------------------------------------------------
# Coupon consumed at payment, not checkout creation (minor fix)
# ---------------------------------------------------------------------------

def test_coupon_increment_moved_to_confirm():
    import inspect

    from infalette_commerce import checkout as mod

    create_src = inspect.getsource(mod.CheckoutService.create_checkout)
    confirm_src = inspect.getsource(mod.CheckoutService._confirm_checkout)
    assert "increment_usage_count" not in create_src.split("# Usage counted")[0].split(
        "Usage counted at payment confirmation"
    )[0]
    assert "increment_usage_count" in confirm_src


# ---------------------------------------------------------------------------
# IG webhook HMAC verifies against raw body bytes (M18)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_hmac_raw_body(monkeypatch):
    import hashlib
    import hmac as hmac_mod

    from infalette_integrations.instagram.webhook import InstagramWebhookHandler

    handler = InstagramWebhookHandler()
    secret = "test-secret"
    monkeypatch.setattr(handler, "_webhook_secret", secret)

    raw = b'{"object":"instagram","entry":[]}'
    good_sig = hmac_mod.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    ok = await handler.verify_webhook_hmac({}, good_sig, raw_body=raw)
    bad = await handler.verify_webhook_hmac({}, "0" * 64, raw_body=raw)
    assert ok is True
    assert bad is False
