"""OAuth social token refresh automation task."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select

from infalette_database.models.social_identity import SocialIdentity
from infalette_integrations.oauth import OAuthManager, store_tokens

logger = logging.getLogger(__name__)

# instagram/whatsapp are both Meta tokens -> same refresh endpoint.
_META_PROVIDERS = {"instagram", "whatsapp"}


async def _refresh_expiring_tokens(days: int = 7) -> dict:
    """Refresh SocialIdentity tokens expiring within `days`.

    Selects identities with expires_at < now()+7d, refreshes each via
    OAuthManager.refresh_access_token, marks 'active' on success and
    'expired' on failure. Commits per row best-effort.
    """
    from infalette_database.session import get_session_factory

    cutoff = datetime.now(timezone.utc) + timedelta(days=days)
    factory = get_session_factory()
    manager = OAuthManager()
    refreshed = 0
    expired = 0
    skipped = 0
    errors: list[str] = []

    async with factory() as session:
        result = await session.execute(
            select(SocialIdentity).where(
                SocialIdentity.expires_at.is_not(None),
                SocialIdentity.expires_at < cutoff,
            )
        )
        identities = list(result.scalars().all())

    for identity in identities:
        try:
            if identity.provider not in _META_PROVIDERS:
                skipped += 1
                continue

            tokens = await manager.refresh_access_token(
                identity.provider, identity.refresh_token or ""
            )
            access_token = tokens.get("access_token")
            if not access_token:
                raise ValueError("refresh response missing access_token")

            expires_in = tokens.get("expires_in")
            expires_dt = None
            if expires_in is not None:
                try:
                    expires_dt = datetime.now(timezone.utc) + timedelta(
                        seconds=int(expires_in)
                    )
                except (TypeError, ValueError):
                    expires_dt = None

            # Persist via the shared upsert helper when we can address the row,
            # otherwise update the loaded identity directly.
            if identity.tenant_id and identity.provider_user_id:
                async with factory() as session:
                    await store_tokens(
                        tenant_id=identity.tenant_id,
                        provider=identity.provider,
                        provider_user_id=identity.provider_user_id,
                        access_token=access_token,
                        refresh_token=tokens.get("refresh_token"),
                        expires_at=expires_dt,
                        session=session,
                    )
            else:
                async with factory() as session:
                    reloaded = await session.get(SocialIdentity, identity.id)
                    if reloaded is None:
                        continue
                    reloaded.access_token = access_token
                    if tokens.get("refresh_token"):
                        reloaded.refresh_token = tokens["refresh_token"]
                    if expires_dt is not None:
                        reloaded.expires_at = expires_dt
                    reloaded.status = "active"
                    await session.commit()
            refreshed += 1
        except Exception as exc:
            logger.error(
                "Token refresh failed for identity %s (%s): %s",
                identity.id,
                identity.provider,
                exc,
                exc_info=True,
            )
            errors.append(f"{identity.id}: {exc}")
            try:
                async with factory() as session:
                    reloaded = await session.get(SocialIdentity, identity.id)
                    if reloaded is not None:
                        reloaded.status = "expired"
                        await session.commit()
                expired += 1
            except Exception as mark_exc:
                logger.error(
                    "Failed to mark identity %s expired: %s", identity.id, mark_exc
                )

    return {
        "identities_found": len(identities),
        "refreshed": refreshed,
        "expired": expired,
        "skipped": skipped,
        "errors": errors,
        "ran_at": datetime.utcnow().isoformat(),
    }


@shared_task(name="apps.workers.tasks.social_tokens.refresh_expiring_social_tokens")
def refresh_expiring_social_tokens() -> dict:
    """Celery entry point for the 6-hourly social token refresh beat task."""
    return asyncio.run(_refresh_expiring_tokens())
