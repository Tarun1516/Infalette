"""Integration base classes."""

from __future__ import annotations

import logging
import uuid as uuid_mod

from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


def allow_unverified_webhooks() -> bool:
    """Whether unverified webhooks may be accepted.

    Fail-open only outside production; in production a missing webhook
    secret must reject the payload rather than silently accept it.
    """
    from infalette_config import get_settings

    env = (getattr(get_settings(), "app_env", "development") or "").lower()
    if env in ("production", "prod"):
        return False
    logger.warning(
        "Webhook secret not configured — accepting UNVERIFIED webhook "
        "(allowed only because app_env != production)"
    )
    return True


def allow_dummy_payments() -> bool:
    """Whether unconfigured payment providers may return dummy responses.

    Only permitted outside production; in production a missing API key must
    raise instead of silently faking a successful payment.
    """
    from infalette_config import get_settings

    env = (getattr(get_settings(), "app_env", "development") or "").lower()
    return env not in ("production", "prod")


class IntegrationClient(ABC):
    """Abstract base class for integration clients."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the integration."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the integration."""
        pass


class IntegrationManager:
    """Manages tenant integrations (persists credentials to the DB)."""

    async def connect_integration(self, tenant_id, integration_type, credentials) -> bool:
        """Create/update a tenant's Integration row for a provider."""
        from sqlalchemy import select

        from infalette_database.models.integration import Integration

        try:
            from infalette_database.session import get_session_factory
        except Exception:
            logger.debug("No session factory available; cannot persist integration")
            return False

        try:
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(Integration).where(
                        Integration.tenant_id == tenant_id,
                        Integration.provider == str(integration_type),
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.credentials_json = dict(credentials or {})
                    existing.status = "active"
                else:
                    session.add(
                        Integration(
                            tenant_id=tenant_id,
                            provider=str(integration_type),
                            credentials_json=dict(credentials or {}),
                            status="active",
                        )
                    )
                await session.commit()
            return True
        except Exception as e:
            logger.error("connect_integration failed for %s/%s: %s", tenant_id, integration_type, e)
            return False

    async def disconnect_integration(self, tenant_id, integration_id) -> bool:
        """Mark a tenant integration inactive."""
        from sqlalchemy import select, update

        from infalette_database.models.integration import Integration
        from infalette_database.session import get_session_factory

        try:
            factory = get_session_factory()
            async with factory() as session:
                iid = (
                    integration_id
                    if isinstance(integration_id, uuid_mod.UUID)
                    else uuid_mod.UUID(str(integration_id))
                )
                await session.execute(
                    update(Integration)
                    .where(
                        Integration.id == iid,
                        Integration.tenant_id == tenant_id,
                    )
                    .values(status="inactive")
                )
                await session.commit()
            return True
        except Exception as e:
            logger.error("disconnect_integration failed: %s", e)
            return False


async def resolve_tenant_channel_token(
    tenant_id,
    provider: str,
    session=None,
) -> dict:
    """Resolve a tenant's stored channel credentials from SocialIdentity.

    Returns ``{"access_token": ..., "provider_user_id": ...}`` — empty
    dict when no connection exists (caller falls back to env tokens).
    Opens its own session when none is supplied (worker contexts).
    """
    try:
        if session is not None:
            return await _lookup_identity(session, tenant_id, provider)
        factory = get_session_factory()
        async with factory() as s:
            return await _lookup_identity(s, tenant_id, provider)
    except Exception as e:
        logger.warning("resolve_tenant_channel_token failed: %s", e)
        return {}


async def _lookup_identity(session, tenant_id, provider: str) -> dict:
    from sqlalchemy import select as _select
    from infalette_database.models.social_identity import SocialIdentity

    row = (
        await session.execute(
            _select(SocialIdentity).where(
                SocialIdentity.tenant_id == tenant_id,
                SocialIdentity.provider == provider,
                SocialIdentity.customer_id.is_(None),  # tenant account, not shopper
            )
        )
    ).scalars().first()
    if row is None or not getattr(row, "access_token", None):
        return {}
    return {
        "access_token": row.access_token,
        "provider_user_id": row.provider_user_id,
    }
