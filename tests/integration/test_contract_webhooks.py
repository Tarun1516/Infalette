"""Contract tests for external payment/social provider webhooks.

These verify that our signature verifiers accept the *exact* payload shape
the providers send, and reject mutated payloads — the real compliance gate.
Run in CI against committed fixtures (no network).
"""
import hashlib
import hmac
import json
import time

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_razorpay_signature_verifies_canonical_body():
    from infalette_integrations.razorpay.client import RazorpayClient
    from infalette_config import get_settings

    # Simulate Razorpay signing: HMAC_SHA256(webhook_secret, raw_body)
    secret = "test_razorpay_webhook_secret"
    payload = {"event": "payment.captured", "payload": {"payment": {"id": "pay_123"}}}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    client = RazorpayClient()
    client._webhook_secret = secret
    assert await client.verify_webhook_signature(payload, sig) is True
    # Tampered payload must fail
    assert await client.verify_webhook_signature({"event": "tampered"}, sig) is False


@pytest.mark.asyncio
async def test_stripe_signature_verifies_timestamped_header_and_rejects_replay():
    from infalette_integrations.stripe.client import StripeClient

    secret = "whsec_test_stripe_secret"
    raw = json.dumps({"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_123"}}}).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"

    client = StripeClient()
    client._webhook_secret = secret
    assert await client.verify_webhook_signature(raw, header) is True

    # Replay with stale timestamp (10 min old) must be rejected
    stale_ts = str(int(time.time()) - 600)
    stale_sig = hmac.new(secret.encode(), f"{stale_ts}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    stale_header = f"t={stale_ts},v1={stale_sig}"
    assert await client.verify_webhook_signature(raw, stale_header, tolerance_seconds=300) is False


@pytest.mark.asyncio
async def test_whatsapp_signature_rejects_unsigned_in_prod(monkeypatch):
    from infalette_integrations.whatsapp.webhook import WhatsAppWebhookHandler
    from infalette_integrations.base import allow_unverified_webhooks

    # In dev, unsigned is tolerated; in prod it must fail (covered by inbound route 403)
    # This contract asserts the handler itself rejects missing HMAC when secret is set
    handler = WhatsAppWebhookHandler()
    handler._webhook_secret = "test_wa_secret"
    # Monkeypatch allow_unverified to False to simulate prod
    import infalette_integrations.whatsapp.webhook as mod
    orig = mod.allow_unverified_webhooks
    mod.allow_unverified_webhooks = lambda: False
    try:
        assert await handler.verify_webhook_hmac({"entry": []}, None, raw_body=b"{}") is False
        assert await handler.verify_webhook_hmac({"entry": []}, "", raw_body=b"{}") is False
    finally:
        mod.allow_unverified_webhooks = orig
