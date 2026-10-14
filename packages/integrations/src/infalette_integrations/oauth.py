"""OAuth manager for social integrations."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_config import get_settings

logger = logging.getLogger(__name__)


def _resolve_client_credentials(provider: str, settings) -> tuple[Optional[str], Optional[str]]:
    """Return (client_id, client_secret) per provider."""
    if provider == "instagram":
        return (settings.social.instagram_client_id, settings.social.instagram_client_secret.get_secret_value() if settings.social.instagram_client_secret else None)
    elif provider == "whatsapp":
        # Try whatsapp-specific client_id/secret if configured, else fallback to instagram credentials
        whatsapp_client_id = getattr(settings.social, "whatsapp_client_id", None)
        whatsapp_client_secret = getattr(settings.social, "whatsapp_client_secret", None)
        # whatsapp_client_secret may be SecretStr
        if hasattr(whatsapp_client_secret, "get_secret_value"):
            whatsapp_client_secret = whatsapp_client_secret.get_secret_value()
        client_id = whatsapp_client_id or settings.social.instagram_client_id
        # Try to get secret similarly
        client_secret_raw = whatsapp_client_secret or settings.social.instagram_client_secret
        if hasattr(client_secret_raw, "get_secret_value"):
            client_secret = client_secret_raw.get_secret_value()
        else:
            client_secret = client_secret_raw
        return (client_id, client_secret)
    else:
        # generic fallback
        cid = getattr(settings.social, f"{provider}_client_id", None) or settings.social.instagram_client_id
        csecret = getattr(settings.social, f"{provider}_client_secret", None) or settings.social.instagram_client_secret
        if hasattr(csecret, "get_secret_value"):
            csecret = csecret.get_secret_value()
        return (cid, csecret)


async def store_tokens(
    tenant_id: UUID,
    provider: str,
    provider_user_id: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime | int],
    session: AsyncSession,
) -> "SocialIdentity":
    """Persist OAuth tokens to SocialIdentity table (create or update).

    Args:
        tenant_id: tenant owning the identity
        provider: e.g. instagram, whatsapp
        provider_user_id: remote user id (instagram user id, wa business id etc.)
        access_token: OAuth access token
        refresh_token: OAuth refresh token (nullable)
        expires_at: datetime or epoch seconds/null
        session: AsyncSession
    """
    from infalette_database.models.social_identity import SocialIdentity

    # Normalize expires_at to datetime
    expires_dt: Optional[datetime] = None
    if isinstance(expires_at, int):
        # Assume epoch seconds or relative seconds (expires_in)? If small, treat as delta
        try:
            if expires_at > 1000000000:  # epoch
                expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
            else:
                expires_dt = datetime.now(timezone.utc) + timedelta(seconds=expires_at)
        except Exception:
            expires_dt = None
    elif isinstance(expires_at, datetime):
        expires_dt = expires_at
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
    else:
        expires_dt = None

    result = await session.execute(
        select(SocialIdentity).where(
            SocialIdentity.tenant_id == tenant_id,
            SocialIdentity.provider == provider,
            SocialIdentity.provider_user_id == provider_user_id,
        )
    )
    identity = result.scalar_one_or_none()
    if identity:
        identity.access_token = access_token
        if refresh_token is not None:
            identity.refresh_token = refresh_token
        identity.expires_at = expires_dt
        identity.status = "active"
        logger.info(f"Updated SocialIdentity for tenant {tenant_id}, provider {provider}, user {provider_user_id}")
    else:
        identity = SocialIdentity(
            tenant_id=tenant_id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_dt,
            status="active",
        )
        session.add(identity)
        logger.info(f"Created SocialIdentity for tenant {tenant_id}, provider {provider}, user {provider_user_id}")

    await session.commit()
    await session.refresh(identity)
    return identity


class OAuthManager:
    """Manages OAuth flows for social integrations."""

    PROVIDERS = {
        "instagram": {
            "auth_url": "https://api.instagram.com/oauth/authorize",
            "token_url": "https://api.instagram.com/oauth/access_token",
            "scope": "user_profile,user_media",
        },
        "whatsapp": {
            "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
            "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
            "scope": "whatsapp_business_management,whatsapp_business_messaging",
        },
    }

    def __init__(self) -> None:
        self._settings = get_settings()

    # In-memory fallback for state when Redis unavailable (per-process)
    _STATE_FALLBACK: dict = {}

    def get_authorization_url(
        self,
        provider: str,
        tenant_id: UUID,
        redirect_uri: str,
    ) -> tuple[str, str]:
        """Get the OAuth authorization URL and state (stores state for CSRF)."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        state = secrets.token_urlsafe(32)
        # Persist state for later validation (Redis with in-memory fallback)
        try:
            import redis as _redis_sync

            from infalette_config import get_settings as _gs

            r = _redis_sync.from_url(_gs().redis.url, decode_responses=True)
            r.setex(f"oauth:state:{state}", 600, f"{provider}:{tenant_id}")
        except Exception:
            self._STATE_FALLBACK[state] = f"{provider}:{tenant_id}"

        client_id, _ = _resolve_client_credentials(provider, self._settings)
        if not client_id:
            raise ValueError(f"OAuth client_id not configured for provider {provider}")

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": provider_info["scope"],
            "response_type": "code",
            "state": state,
        }

        import urllib.parse
        auth_url = f"{provider_info['auth_url']}?{urllib.parse.urlencode(params)}"

        return auth_url, state

    async def exchange_code_for_token(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange code for token, then upgrade to long-lived where applicable."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        client_id, client_secret = _resolve_client_credentials(provider, self._settings)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider_info["token_url"],
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            tokens = response.json()

        # Upgrade to long-lived tokens (best-effort; short-lived still works)
        try:
            short_token = tokens.get("access_token")
            if short_token and provider == "instagram":
                async with httpx.AsyncClient() as client2:
                    r2 = await client2.get(
                        "https://graph.instagram.com/access_token",
                        params={
                            "grant_type": "ig_exchange_token",
                            "client_secret": client_secret,
                            "access_token": short_token,
                        },
                    )
                    if r2.status_code == 200:
                        ll = r2.json()
                        tokens["access_token"] = ll.get("access_token", short_token)
                        tokens["expires_in"] = ll.get("expires_in", tokens.get("expires_in"))
                        tokens["token_type"] = ll.get("token_type", "bearer")
            elif short_token and provider == "whatsapp":
                async with httpx.AsyncClient() as client2:
                    r2 = await client2.get(
                        "https://graph.facebook.com/v18.0/oauth/access_token",
                        params={
                            "grant_type": "fb_exchange_token",
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "fb_exchange_token": short_token,
                        },
                    )
                    if r2.status_code == 200:
                        ll = r2.json()
                        tokens["access_token"] = ll.get("access_token", short_token)
                        tokens["expires_in"] = ll.get("expires_in", tokens.get("expires_in"))
        except Exception as e:
            logger.warning(f"Long-lived token exchange failed for {provider}: {e}")

        return tokens

    async def refresh_access_token(
        self,
        provider: str,
        refresh_token: str,
    ) -> dict:
        """Refresh an access token (provider-specific)."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        client_id, client_secret = _resolve_client_credentials(provider, self._settings)

        if provider == "instagram":
            # Instagram uses GET refresh_access_token with the *access* token
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.instagram.com/refresh_access_token",
                    params={
                        "grant_type": "ig_refresh_token",
                        "access_token": refresh_token,
                    },
                )
                response.raise_for_status()
                return response.json()
        elif provider == "whatsapp":
            # Facebook long-lived tokens are refreshed by re-exchanging
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.facebook.com/v18.0/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "fb_exchange_token": refresh_token,
                    },
                )
                response.raise_for_status()
                return response.json()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider_info["token_url"],
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "ig_refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()

    async def revoke_access_token(
        self,
        provider: str,
        access_token: str,
    ) -> bool:
        """Revoke an access token."""
        provider_info = self.PROVIDERS.get(provider)
        if not provider_info:
            raise ValueError(f"Unknown provider: {provider}")

        client_id, client_secret = _resolve_client_credentials(provider, self._settings)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider_info["token_url"],
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "access_token": access_token,
                    "method": "delete",
                },
            )
            return response.status_code == 200

    async def store_tokens(
        self,
        tenant_id: UUID,
        provider: str,
        provider_user_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[datetime | int],
        session: AsyncSession,
    ) -> "SocialIdentity":
        """Store OAuth tokens (persist to DB). Instance method delegates to module function."""
        return await store_tokens(tenant_id, provider, provider_user_id, access_token, refresh_token, expires_at, session)

    # Keep legacy sync signature for backward compat — now persists for real
    def store_tokens_sync(
        self,
        tenant_id: UUID,
        provider: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[int],
    ) -> None:
        """Synchronous wrapper that persists tokens via its own DB session."""
        import asyncio

        from infalette_database.session import get_session_factory

        async def _run() -> None:
            factory = get_session_factory()
            async with factory() as session:
                await store_tokens(
                    tenant_id,
                    provider,
                    provider_user_id=None,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    session=session,
                )

        asyncio.run(_run())

    async def handle_oauth_callback(
        self,
        provider: str,
        code: str,
        state: str,
        redirect_uri: str,
        session: AsyncSession,
        tenant_id: Optional[UUID] = None,
    ) -> dict:
        """Handle the OAuth callback.

        Exchanges code, persists tokens if tenant_id and session provided.
        """
        tokens = await self.exchange_code_for_token(provider, code, redirect_uri)

        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in")
        user_id = tokens.get("user_id") or tokens.get("id") or tokens.get("provider_user_id") or "unknown"

        # Try to persist if we have tenant context and session
        if tenant_id and session and access_token:
            try:
                expires_at_val = None
                if expires_in:
                    try:
                        expires_at_val = int(expires_in)
                    except Exception:
                        expires_at_val = None
                await store_tokens(tenant_id, provider, str(user_id), access_token, refresh_token, expires_at_val, session)
            except Exception as e:
                logger.error(f"Failed to persist OAuth tokens for tenant {tenant_id}: {e}", exc_info=True)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "user_id": user_id,
        }

    def get_oauth_state(self, state: str) -> bool:
        """Validate the OAuth state parameter (CSRF)."""
        if not state or len(state) < 16:
            return False
        try:
            import redis as _redis_sync

            from infalette_config import get_settings as _gs

            r = _redis_sync.from_url(_gs().redis.url, decode_responses=True)
            val = r.get(f"oauth:state:{state}")
            if val:
                r.delete(f"oauth:state:{state}")
                return True
        except Exception:
            pass
        # Fallback in-memory
        return bool(self._STATE_FALLBACK.pop(state, None))
