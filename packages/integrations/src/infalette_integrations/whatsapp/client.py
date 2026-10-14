"""WhatsApp Cloud API client."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

import httpx

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Client for the WhatsApp Cloud API."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
    ) -> None:
        self._settings = get_settings()
        # Per-tenant credentials (from SocialIdentity) take precedence;
        # env/config token is the platform-level fallback.
        self._token = access_token or self._settings.social.whatsapp_token
        self._phone_number_id = (
            phone_number_id or self._settings.social.whatsapp_phone_number_id
        )

    def set_access_token(self, token: str, phone_number_id: str | None = None) -> None:
        """Bind this client to a tenant's stored credentials."""
        if token:
            self._token = token
        if phone_number_id:
            self._phone_number_id = phone_number_id

    async def send_message(
        self,
        to: str,
        message: str,
        preview_url: bool = False,
    ) -> dict:
        """Send a text message via WhatsApp."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{self._phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self._token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "text": {"body": message, "preview_url": preview_url},
                },
            )
            response.raise_for_status()
            return response.json()

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        template_data: list[str],
        language: str = "en",
    ) -> dict:
        """Send a template message via WhatsApp."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{self._phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self._token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": language},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": d} for d in template_data],
                            }
                        ],
                    },
                },
            )
            response.raise_for_status()
            return response.json()

    async def create_flow(
        self,
        flow_name: str,
        flow_data: dict,
    ) -> dict:
        """Create a WhatsApp Flow."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{self._phone_number_id}/flows",
                headers={"Authorization": f"Bearer {self._token}"},
                json={
                    "name": flow_name,
                    "data": flow_data,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_flow(self, flow_id: str) -> dict:
        """Get a WhatsApp Flow by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{flow_id}",
                headers={"Authorization": f"Bearer {self._token}"},
            )
            response.raise_for_status()
            return response.json()

    async def update_flow(self, flow_id: str, flow_data: dict) -> dict:
        """Update a WhatsApp Flow."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{flow_id}",
                headers={"Authorization": f"Bearer {self._token}"},
                json=flow_data,
            )
            response.raise_for_status()
            return response.json()

    async def get_message_status(self, message_id: str) -> dict:
        """Get the status of a WhatsApp message."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/{message_id}",
                headers={"Authorization": f"Bearer {self._token}"},
            )
            response.raise_for_status()
            return response.json()

    async def handle_webhook_verification(
        self,
        mode: str,
        verify_token: str,
        challenge: str,
    ) -> Optional[str]:
        """Verify the webhook."""
        expected_token = self._settings.social.whatsapp_verify_token
        if mode == "subscribe" and verify_token == expected_token:
            return challenge
        return None
