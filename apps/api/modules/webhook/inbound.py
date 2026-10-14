"""Inbound provider webhooks — payments (Razorpay/Stripe) + Meta (Instagram/WhatsApp) + Clerk.

These endpoints are unauthenticated by design: authenticity comes from
provider signatures (HMAC) / Meta subscription verification, per
docs/requirements.md §8 ("Never trust the browser redirect as proof of
payment. The signed payment webhook is authoritative.").
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------- payments
@router.post("/payments/{provider}", response_model=dict)
async def payment_webhook(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Receive Razorpay/Stripe payment webhooks and confirm orders.

    Signature headers: ``X-Razorpay-Signature`` / ``Stripe-Signature``.
    The checkout id arrives inside notes/metadata (attached when the
    payment link/session was created).
    """
    provider_norm = provider.lower().strip()
    if provider_norm not in ("razorpay", "stripe"):
        raise HTTPException(status_code=404, detail=f"Unknown payment provider: {provider}")

    try:
        raw = await request.body()
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    signature = (
        request.headers.get("X-Razorpay-Signature")
        or request.headers.get("X-Razorpay-Signature".lower())
        or request.headers.get("stripe-signature")
        or request.headers.get("Stripe-Signature")
        or ""
    )

    from infalette_commerce.checkout import CheckoutService

    svc = CheckoutService()
    try:
        await svc.process_payment_webhook(
            provider_norm,
            payload,
            signature,
            session,
            raw_body=raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw),
        )
    except ValueError as e:
        # Verification failures must not be swallowed (alerting relies on 4xx)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("payment webhook processing failed")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"received": True, "provider": provider_norm}


# --------------------------------------------------------------- instagram
@router.get("/instagram")
async def instagram_verify(
    mode: str = Query(alias="hub.mode", default=None),
    verify_token: str = Query(alias="hub.verify_token", default=None),
    challenge: str = Query(alias="hub.challenge", default=None),
):
    """Meta subscription handshake (hub.challenge echo)."""
    if not challenge:
        return {"status": "instagram webhook endpoint ready"}
    return await _ig_verify(mode, verify_token, challenge)


async def _ig_verify(mode, verify_token, challenge):
    from infalette_integrations.instagram.webhook import InstagramWebhookHandler

    result = await InstagramWebhookHandler().verify_webhook(mode, verify_token, challenge)
    if result is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    # Must return the plain challenge body per Meta docs
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(content=result)


async def _ig_receive(request: Request, session: AsyncSession):
    raw = await request.body()
    try:
        import json as _json

        payload = _json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from infalette_integrations.instagram.webhook import InstagramWebhookHandler

    handler = InstagramWebhookHandler()
    signature = request.headers.get("X-Hub-Signature-256", "")
    # Meta signs the raw body; a missing signature is a rejection outside
    # local/dev (allow_unverified_webhooks gates that escape hatch).
    if not signature:
        raise HTTPException(status_code=403, detail="Missing X-Hub-Signature-256")
    if not await handler.verify_webhook_hmac(
        payload, signature.removeprefix("sha256="), raw_body=raw
    ):
        raise HTTPException(status_code=403, detail="Signature verification failed")

    object_kind = payload.get("object") or payload.get("field") or ""
    results = []
    entry_list = payload.get("entry", [])
    for entry in entry_list:
        changes = entry.get("changes") or []
        for change in changes:
            value = change.get("value", {})
            kind = change.get("field") or change.get("property") or object_kind
            if "comments" in str(kind) or value.get("comment"):
                results.append(await handler.process_comment_webhook(payload, session))
                break
            if "messages" in str(kind) or value.get("message"):
                results.append(await handler.process_dm_webhook(payload, session))
                break
        else:
            continue
        break
    if not results:
        # Fallback: let the handler decide based on full payload shape
        if any((e.get("changes") or [{}])[0].get("value", {}).get("comment") for e in entry_list):
            results.append(await handler.process_comment_webhook(payload, session))
        else:
            results.append(await handler.process_dm_webhook(payload, session))

    # Automation engine pass (best-effort; handler may already trigger)
    return {"received": True, "processed": len(results), "detail": results}


@router.post("/instagram")
async def instagram_receive(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Receive Instagram comment/DM events -> conversations -> automation."""
    return await _ig_receive(request, session)


# ---------------------------------------------------------------- whatsapp
@router.get("/whatsapp")
async def whatsapp_verify(
    mode: str = Query(alias="hub.mode", default=None),
    verify_token: str = Query(alias="hub.verify_token", default=None),
    challenge: str = Query(alias="hub.challenge", default=None),
):
    """Meta/WhatsApp Cloud API subscription handshake."""
    if not challenge:
        return {"status": "whatsapp webhook endpoint ready"}
    from infalette_integrations.whatsapp.webhook import WhatsAppWebhookHandler

    result = await WhatsAppWebhookHandler().verify_webhook(mode, verify_token, challenge)
    if result is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(content=result)


@router.post("/whatsapp")
async def whatsapp_receive(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Receive WhatsApp message/status events -> conversations -> automation."""
    raw_body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from infalette_integrations.whatsapp.webhook import WhatsAppWebhookHandler

    handler = WhatsAppWebhookHandler()

    # Meta signs WA payloads with X-Hub-Signature-256 over the raw bytes,
    # exactly like Instagram. Reject unsigned/spoofed requests.
    signature = request.headers.get("X-Hub-Signature-256")
    if not await handler.verify_webhook_hmac(payload, signature, raw_body=raw_body):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        result = await handler.process_message_webhook(payload, session)
    except Exception:  # pragma: no cover - defensive
        logger.exception("whatsapp webhook processing failed")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"received": True, "detail": result}


# ------------------------------------------------------------------- clerk
@router.post("/clerk", response_model=dict)
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Sync Clerk users into Neon (``users`` table).

    Configure in the Clerk Dashboard → Webhooks:
        URL: https://<api>/api/v1/webhooks/clerk
        Events: user.created, user.updated, user.deleted
        Signing secret → env ``CLERK_WEBHOOK_SECRET``.

    Verification uses Svix headers (``svix-id`` / ``svix-timestamp`` /
    ``svix-signature``). When ``CLERK_WEBHOOK_SECRET`` is unset (local dev
    without Clerk), the payload is accepted unverified and a warning is
    logged — never do this in production.
    """
    raw = await request.body()
    try:
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from infalette_config import get_settings

    settings = get_settings()
    webhook_secret = getattr(getattr(settings, "clerk", None), "webhook_secret", None)
    secret_value = webhook_secret.get_secret_value() if webhook_secret else None

    if secret_value:
        verified = _verify_svix(
            secret_value,
            request.headers.get("svix-id", ""),
            request.headers.get("svix-timestamp", ""),
            request.headers.get("svix-signature", ""),
            raw,
        )
        if not verified:
            raise HTTPException(status_code=403, detail="Invalid Clerk webhook signature")
    else:
        logger.warning("CLERK_WEBHOOK_SECRET unset — accepting Clerk webhook unverified (dev only)")

    event_type = payload.get("type", "")
    data = payload.get("data", {}) or {}

    from infalette_database.models.user import User, UserStatus

    clerk_user_id = data.get("id", "")
    email_addresses = data.get("email_addresses") or []
    primary_email_id = data.get("primary_email_address_id")
    email = None
    for e in email_addresses:
        if e.get("id") == primary_email_id or not email:
            email = e.get("email_address")
            if e.get("id") == primary_email_id:
                break
    if not email and email_addresses:
        email = email_addresses[0].get("email_address")

    try:
        if event_type == "user.deleted":
            if clerk_user_id:
                row = (
                    await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
                ).scalar_one_or_none()
                if row is not None:
                    row.status = UserStatus.DELETED
                    await session.commit()
            return {"received": True, "event": event_type}

        if event_type in ("user.created", "user.updated"):
            if not clerk_user_id or not email:
                raise HTTPException(status_code=422, detail="Clerk payload missing id/email")
            email_norm = email.lower().strip()
            # 1. Match by clerk id, 2. fall back to email (pre-Clerk accounts).
            user = (
                await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
            ).scalar_one_or_none()
            if user is None:
                user = (
                    await session.execute(select(User).where(User.email == email_norm))
                ).scalar_one_or_none()
            first = data.get("first_name") or ""
            last = data.get("last_name") or ""
            if user is None:
                # New Clerk user → create a customer-scoped row. Tenant
                # assignment happens at first storefront login via X-Tenant;
                # keep tenant NULL until then (column is nullable).
                user = User(
                    clerk_user_id=clerk_user_id,
                    email=email_norm,
                    password_hash=None,
                    first_name=first or email_norm.split("@")[0],
                    last_name=last or "",
                    role="customer",
                    status=UserStatus.ACTIVE,
                )
                session.add(user)
            else:
                user.clerk_user_id = clerk_user_id
                user.email = email_norm
                if first:
                    user.first_name = first
                if last:
                    user.last_name = last
                if str(getattr(user.status, "value", user.status)) == "deleted":
                    user.status = UserStatus.ACTIVE
            await session.commit()
            return {"received": True, "event": event_type, "user": email_norm}

        # Unknown Clerk event — acknowledge so Clerk stops retrying.
        return {"received": True, "event": event_type, "ignored": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("clerk webhook processing failed")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


def _verify_svix(secret: str, msg_id: str, msg_ts: str, msg_sig: str, payload: bytes) -> bool:
    """Verify a Svix-signed webhook without the svix SDK.

    Svix signs ``{msg_id}.{msg_ts}.{payload}`` with HMAC-SHA256 using the
    base64-decoded secret (after stripping the ``whsec_`` prefix). The
    ``svix-signature`` header may carry multiple space-separated versions;
    any ``v1,<b64>`` match accepts.
    """
    import base64
    import hashlib
    import hmac

    if not (secret and msg_id and msg_ts and msg_sig and payload is not None):
        return False
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"))
        signed = f"{msg_id}.{msg_ts}.".encode() + payload
        expected = hmac.new(key, signed, hashlib.sha256).digest()
        for part in msg_sig.split():
            if "," not in part:
                continue
            version, sig_b64 = part.split(",", 1)
            if version.strip() != "v1":
                continue
            try:
                candidate = base64.b64decode(sig_b64.strip())
            except Exception:
                continue
            if hmac.compare_digest(candidate, expected):
                return True
        return False
    except Exception:
        return False
