"""Instagram API client."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

import httpx

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class InstagramClient:
    """Client for the Instagram Graph API."""

    BASE_URL = "https://graph.instagram.com/v18.0"

    def __init__(self, access_token: Optional[str] = None) -> None:
        self._settings = get_settings()
        # Fix: previously incorrectly assigned client_secret to access_token.
        # Now correctly resolve access_token: explicit arg, then env/config, else None (must be set per-tenant).
        if access_token:
            self._access_token = access_token
        else:
            # Try to find a configured Instagram access token (if any), but do not use client_secret
            self._access_token = getattr(self._settings.social, "instagram_access_token", None)
            if hasattr(self._access_token, "get_secret_value"):
                self._access_token = self._access_token.get_secret_value()
            # For backward compat, if still None try explicit token setting (but never secret)
            if self._access_token is None:
                # Support fetching from DB via helper if needed - caller should set via set_access_token
                self._access_token = None

        # Keep client_secret separate for OAuth operations
        secret = self._settings.social.instagram_client_secret
        self._client_secret = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
        self._client_id = self._settings.social.instagram_client_id

    def set_access_token(self, token: str) -> None:
        """Set access token dynamically (e.g., per-tenant token from DB)."""
        self._access_token = token

    async def get_instagram_user(self, ig_user_id: str) -> dict:
        """Get Instagram user info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{ig_user_id}",
                params={"access_token": self._access_token, "fields": "id,username,media_count,followers_count"},
            )
            response.raise_for_status()
            return response.json()

    async def get_comments(self, media_id: str, limit: int = 50) -> list[dict]:
        """Get comments on a media post."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{media_id}/comments",
                params={"access_token": self._access_token, "limit": limit},
            )
            response.raise_for_status()
            return response.json().get("data", [])

    async def send_reply(self, comment_id: str, message: str) -> dict:
        """Reply to a comment."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{comment_id}/replies",
                params={"access_token": self._access_token, "message": message},
            )
            response.raise_for_status()
            return response.json()

    async def send_dm(self, ig_user_id: str, recipient_id: str, message: str) -> dict:
        """Send a direct message."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{ig_user_id}/messages",
                params={"access_token": self._access_token},
                json={"recipient_users": [recipient_id], "message": message},
            )
            response.raise_for_status()
            return response.json()

    async def get_media_insights(self, media_id: str) -> dict:
        """Get insights for a media post."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{media_id}/insights",
                params={"access_token": self._access_token, "metric": "engagement,impressions,reach"},
            )
            response.raise_for_status()
            return response.json()

    async def get_account_insights(self, ig_user_id: str, period: str = "day") -> dict:
        """Get account-level insights."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{ig_user_id}/insights",
                params={"access_token": self._access_token, "metric": "follower_count,impressions,reach", "period": period},
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self) -> dict:
        """Refresh the Instagram access token."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/refresh_access_token",
                params={"access_token": self._access_token, "grant_type": "ig_refresh_token"},
            )
            response.raise_for_status()
            return response.json()

    async def handle_rate_limits(self, response: httpx.Response) -> bool:
        """Check rate limit headers and return if rate limited."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 10:
            logger.warning(f"Instagram API rate limit low: {remaining} remaining")
        return response.status_code == 429
