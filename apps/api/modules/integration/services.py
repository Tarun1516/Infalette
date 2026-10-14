"""Integration management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.integration import Integration
from infalette_integrations.razorpay.client import RazorpayClient
from infalette_integrations.stripe.client import StripeClient
from infalette_config import get_settings


async def list_integrations(
    tenant_id: UUID,
    session: AsyncSession,
    provider: Optional[str] = None,
) -> list[Integration]:
    """List integrations for a tenant."""
    query = select(Integration).where(Integration.tenant_id == tenant_id)
    if provider:
        query = query.where(Integration.provider == provider)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_integration(
    tenant_id: UUID,
    integration_id: UUID,
    session: AsyncSession,
) -> Integration | None:
    """Get an integration by ID."""
    result = await session.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_integration(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Integration:
    """Create a new integration."""
    integration = Integration(
        tenant_id=tenant_id,
        provider=data.get("provider"),
        name=data.get("name"),
        config=data.get("config", {}),
        status=data.get("status", "active"),
        credentials=data.get("credentials", {}),
    )
    session.add(integration)
    await session.commit()
    await session.refresh(integration)
    return integration


async def update_integration(
    tenant_id: UUID,
    integration_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Integration | None:
    """Update an integration."""
    integration = await get_integration(tenant_id, integration_id, session)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    for key, value in data.items():
        if hasattr(integration, key) and value is not None:
            setattr(integration, key, value)

    await session.commit()
    await session.refresh(integration)
    return integration


async def delete_integration(
    tenant_id: UUID,
    integration_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete an integration."""
    await session.execute(
        delete(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def test_integration(
    tenant_id: UUID,
    integration_id: UUID,
    session: AsyncSession,
) -> dict:
    """Test an integration connection with a real provider call where possible."""
    integration = await get_integration(tenant_id, integration_id, session)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    creds = integration.credentials_json or {}

    if integration.provider == "razorpay":
        client = RazorpayClient()
        key_id = creds.get("key_id") or client._key_id
        key_secret = creds.get("key_secret") or client._key_secret
        if not key_id or not key_secret:
            return {
                "status": "error",
                "message": "Razorpay key_id/key_secret not configured",
            }
        import httpx

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    "https://api.razorpay.com/v1/payments?count=1",
                    auth=(str(key_id), str(key_secret)),
                    timeout=10,
                )
            if resp.status_code == 200:
                return {"status": "success", "message": "Razorpay credentials verified"}
            return {
                "status": "error",
                "message": f"Razorpay rejected credentials (HTTP {resp.status_code})",
            }
        except Exception as e:
            return {"status": "error", "message": f"Razorpay unreachable: {e}"}

    elif integration.provider == "stripe":
        client = StripeClient()
        secret = creds.get("secret_key") or client._secret_key
        if not secret:
            return {"status": "error", "message": "Stripe secret_key not configured"}
        import httpx

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    "https://api.stripe.com/v1/balance",
                    headers={"Authorization": f"Bearer {secret}"},
                    timeout=10,
                )
            if resp.status_code == 200:
                return {"status": "success", "message": "Stripe credentials verified"}
            return {
                "status": "error",
                "message": f"Stripe rejected credentials (HTTP {resp.status_code})",
            }
        except Exception as e:
            return {"status": "error", "message": f"Stripe unreachable: {e}"}

    elif integration.provider in ("email", "sms"):
        settings = get_settings()
        group = getattr(settings, integration.provider)
        configured = bool(getattr(group, "smtp_host", None) or getattr(group, "endpoint_url", None) or getattr(group, "api_key", None))
        if configured:
            return {"status": "success", "message": f"{integration.provider} delivery configured"}
        return {"status": "error", "message": f"{integration.provider} provider not configured"}

    else:
        return {"status": "unknown", "message": f"Unknown provider: {integration.provider}"}


async def get_available_providers() -> list[dict]:
    """Get list of available integration providers."""
    return [
        {"id": "razorpay", "name": "Razorpay", "type": "payment"},
        {"id": "stripe", "name": "Stripe", "type": "payment"},
        {"id": "email", "name": "Email (SES)", "type": "email"},
        {"id": "instagram", "name": "Instagram", "type": "social"},
        {"id": "whatsapp", "name": "WhatsApp", "type": "social"},
    ]
