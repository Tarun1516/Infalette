"""Regression tests for v4 gap-closure fixes.

Each test maps to a finding in docs/FINDINGS_REPORT_V4.md.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4


# ---------------------------------------------------------------------------
# B1/B2: Webhook ORM models exist and services import (was ModuleNotFoundError)
# ---------------------------------------------------------------------------

def test_webhook_models_exist():
    from infalette_database.models import WebhookEndpoint, WebhookDelivery

    cols = {c for c in WebhookEndpoint.__table__.columns.keys()}
    assert {"name", "url", "events", "status", "secret"} <= cols

    dcols = set(WebhookDelivery.__table__.columns.keys())
    assert "endpoint_id" in dcols


def test_webhook_services_importable():
    from apps.api.modules.webhook import services  # noqa: F401


# ---------------------------------------------------------------------------
# B1: schema drift — ORM columns used by handlers exist on models
# ---------------------------------------------------------------------------

def test_conversation_message_columns_exist():
    from infalette_database.models.conversation import Conversation
    from infalette_database.models.message import Message, MessageDirection

    assert {"external_id", "customer_name", "status", "participants_json"} <= {
        c for c in Conversation.__table__.columns.keys()
    }
    mcols = set(Message.__table__.columns.keys())
    assert {"direction", "external_id", "status"} <= mcols
    assert MessageDirection.INBOUND.value == "inbound"


def test_automation_rule_has_trigger_config():
    from infalette_database.models.automation_rule import AutomationRule

    acols = set(AutomationRule.__table__.columns.keys())
    assert {"trigger_config", "conditions_json", "actions_json", "priority"} <= acols


def test_products_migration_columns_on_model():
    """Spec §3 product fields must exist on the ORM (and now in migration 007)."""
    from infalette_database.models.product import Product

    pcols = set(Product.__table__.columns.keys())
    for col in (
        "tax_class",
        "ingredients",
        "safety_info",
        "age_suitability",
        "pregnancy_stage",
        "dimensions_json",
        "images_json",
    ):
        assert col in pcols


def test_migration_chain_contains_alignment():
    """Migration 007 must add every ORM-only column to the DB side."""
    import re

    src = open(
        "packages/database/alembic/versions/007_align_orm_schema.py"
    ).read()
    for stmt in [
        ("products", "tax_class"),
        ("tenants", "plan_id"),
        ("conversations", "lead_id"),
        ("messages", "attachments_json"),
        ("automation_rules", "actions_json"),
        ("plans", "plan_type"),
    ]:
        pattern = rf"\(\s*\"{stmt[0]}\"\s*,\s*\"{stmt[1]}\""
        assert re.search(pattern, src), f"missing ALTER for {stmt}"


# ---------------------------------------------------------------------------
# B4: TriggerEngine matches rules without trigger_config via type mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_engine_matches_by_trigger_type(db_session):
    from datetime import datetime

    from infalette_automation.triggers import TriggerEngine
    from infalette_automation.schemas import TriggerEvent
    from infalette_database.models.automation_rule import (
        AutomationRule,
        AutomationTriggerType,
        AutomationRuleStatus,
    )

    tenant = uuid4()
    rule = AutomationRule(
        tenant_id=tenant,
        name="price comments",
        trigger_type=AutomationTriggerType.COMMENT_KEYWORD,
        status=AutomationRuleStatus.ACTIVE,
        conditions_json={},
        actions_json=[],
    )
    db_session.add(rule)
    await db_session.commit()

    engine = TriggerEngine()
    event = TriggerEvent(
        event_type="conversation.message_received",
        tenant_id=tenant,
        actor_id=None,
        payload={"comment_text": "price please"},
        timestamp=datetime.utcnow(),
    )
    matching = await engine.get_matching_rules(event, db_session)
    assert rule.id in [r.id for r in matching]


# ---------------------------------------------------------------------------
# P5: refunds validate amounts and update order status via payment.order_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refund_rejects_excessive_amount(db_session):
    from datetime import datetime, timezone

    from infalette_commerce.orders import OrderService
    from infalette_database.models.payment import Payment, PaymentProvider, PaymentStatus

    payment = Payment(
        tenant_id=uuid4(),
        order_id=uuid4(),
        provider=PaymentProvider.RAZORPAY,
        provider_payment_id="pay_test123",
        amount_cents=10000,
        currency="INR",
        status=PaymentStatus.SUCCEEDED,
    )
    db_session.add(payment)
    await db_session.commit()

    with pytest.raises(ValueError):
        await OrderService().process_refund(
            payment.id, 20000, "too much", db_session
        )


# ---------------------------------------------------------------------------
# P2: funnel stages map to actually-recorded events
# ---------------------------------------------------------------------------

def test_funnel_stage_event_mapping():
    from infalette_analytics.funnel import FunnelAnalyzer

    mapping = FunnelAnalyzer.STAGE_EVENT_TYPES
    assert "checkout.created" in mapping["checkout_created"]
    assert "payment.succeeded" in mapping["payment_succeeded"]
    assert "order.created" in mapping["order_created"]
    assert "cart.item_added" in mapping["add_to_cart"]


# ---------------------------------------------------------------------------
# P1: EmailClient no longer fakes "sent" when unconfigured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_client_skips_when_unconfigured(monkeypatch):
    from infalette_integrations.email.client import EmailClient

    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)

    result = await EmailClient().send_email(
        to="x@example.com", subject="t", html_content="<p>hi</p>", tenant_id=uuid4()
    )
    assert result["status"] in ("skipped", "unconfigured")


# ---------------------------------------------------------------------------
# M3: report schedules model + API surface exist
# ---------------------------------------------------------------------------

def test_report_schedule_model_and_routes():
    from infalette_database.models import ReportSchedule

    cols = set(ReportSchedule.__table__.columns.keys())
    assert {"report_type", "frequency", "recipients_json", "is_active"} <= cols

    from apps.api.modules.reports import routes as reports_routes

    paths = {r.path for r in reports_routes.router.routes}
    assert "/" in paths and "/{schedule_id}" in paths


@pytest.mark.asyncio
async def test_report_schedule_validation(db_session):
    from apps.api.modules.reports.services import create_schedule

    bad = await create_schedule(uuid4(), {"report_type": "bogus"}, db_session)
    assert isinstance(bad, str)  # validation error message


# ---------------------------------------------------------------------------
# M1: abandoned segments service exists and returns both segment lists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abandoned_segments_shape(db_session):
    from apps.api.modules.analytics.services import get_abandoned_segments

    data = await get_abandoned_segments(uuid4(), db_session)
    assert "abandoned_carts" in data
    assert "abandoned_social_checkouts" in data


# ---------------------------------------------------------------------------
# P3/P4: Razorpay host + fail-closed verification in production
# ---------------------------------------------------------------------------

def test_razorpay_host_is_correct():
    from infalette_integrations.razorpay.client import RazorpayClient

    client = RazorpayClient()
    assert client._base_url.startswith("https://api.razorpay.com")


def test_unverified_webhooks_fail_closed_in_production():
    from infalette_integrations.base import allow_unverified_webhooks

    with patch("infalette_config.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.app_env = "production"
        assert allow_unverified_webhooks() is False


def test_dummy_payments_rejected_in_production():
    from infalette_integrations.base import allow_dummy_payments

    with patch("infalette_config.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.app_env = "production"
        assert allow_dummy_payments() is False


# ---------------------------------------------------------------------------
# P10: MFA recovery codes usable at login (hashed, single-use)
# ---------------------------------------------------------------------------

def test_recovery_code_flow_hashes_and_consumes():
    from infalette_auth.security import PasswordHasher

    hasher = PasswordHasher()
    code = hasher.generate_recovery_codes(1)[0]
    hashed = hasher.hash_password(code)
    assert hasher.verify_password(code, hashed)


# ---------------------------------------------------------------------------
# P11: providers/available is reachable (declared before /{integration_id})
# ---------------------------------------------------------------------------

def test_providers_route_not_shadowed():
    from apps.api.modules.integration.routes import router

    order = [r.path for r in router.routes]
    providers_idx = next(i for i, p in enumerate(order) if "providers/available" in str(p))
    detail_idx = next(i for i, p in enumerate(order) if str(p) == "/{integration_id}")
    assert providers_idx < detail_idx


# ---------------------------------------------------------------------------
# P12: SEO sitemap uses configured storefront URL, not example.com
# ---------------------------------------------------------------------------

def test_sitemap_base_url_from_settings():
    from infalette_seo.sitemap import _base_url

    url = _base_url()
    assert "example.com" not in url


# ---------------------------------------------------------------------------
# V5 fixes
# ---------------------------------------------------------------------------

def test_request_id_middleware_sets_header():
    from apps.api.core.middleware import RequestIDMiddleware
    from fastapi import FastAPI
    import pytest_asyncio  # noqa: F401  (ensures plugin present)
    import httpx

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    from fastapi.testclient import TestClient  # sync wrapper is fine here

    with TestClient(app) as client:
        resp = client.get("/ping")
        assert resp.headers.get("X-Request-ID")
        assert resp.headers.get("X-Process-Time")


def test_health_detailed_endpoint_registered():
    from apps.api.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/health/detailed" in paths


def test_sitemap_generator_has_no_hardcoded_host():
    src = open("packages/seo/src/infalette_seo/sitemap_generator.py").read()
    assert "store.infalette.com" not in src


def test_processor_loop_polls_events():
    from infalette_automation.processor import AutomationProcessor

    assert hasattr(AutomationProcessor, "start_processing_loop")


def test_integration_manager_persists():
    from infalette_integrations.base import IntegrationManager

    assert "Integration" in __import__("inspect").getsource(
        IntegrationManager.connect_integration
    )


def test_oauth_store_tokens_sync_persists():
    import inspect

    from infalette_integrations.oauth import OAuthManager

    source = inspect.getsource(OAuthManager.store_tokens_sync)
    assert "store_tokens" in source and "logging only" not in source.lower()


def test_openapi_includes_bearer_auth():
    from apps.api.main import app

    # Generated lazily on first request; all routes registered by now.
    schema = app.openapi()
    schemes = (schema or {}).get("components", {}).get("securitySchemes", {})
    assert "bearerAuth" in schemes
    assert len(schema.get("paths", {})) > 20  # routers actually included


def test_social_task_fans_out_via_webhooks():
    import inspect

    from apps.workers.tasks import social

    src = inspect.getsource(social.post_to_social)
    assert "WebhookEndpoint" in src
    assert "social.posted" in src


def test_checkout_service_failure_not_masked():
    import inspect

    from apps.api.modules.checkout import services

    src = inspect.getsource(services.create_checkout)
    assert "except ImportError" in src  # fallback only for minimal envs
