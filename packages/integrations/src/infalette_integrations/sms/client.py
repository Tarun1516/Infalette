"""SMS integration client."""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

import httpx

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class SMSClient:
    """Client for sending SMS via settings-driven generic HTTP providers.

    Supports ``msg91``-style JSON payloads, ``twilio``-style form posts,
    and a ``generic`` JSON provider, configured through ``settings.sms``.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        sms = self._settings.sms
        self._provider = sms.provider
        self._api_key = sms.api_key.get_secret_value() if sms.api_key else None
        self._sender_id = sms.sender_id
        self._endpoint_url = sms.endpoint_url
        self._enabled = sms.enabled

    async def send_sms(
        self,
        to: str,
        message: str,
        tenant_id: Optional[UUID] = None,
    ) -> dict:
        """Send an SMS via the configured provider.

        Returns ``{"status": "skipped", ...}`` when SMS is disabled so
        tests/dev environments never hang on outbound calls.
        """
        if not self._enabled:
            return {"status": "skipped", "reason": "sms_disabled"}

        if not self._endpoint_url:
            logger.error("SMS endpoint URL is not configured")
            return {"status": "failed", "error": "sms_endpoint_not_configured"}

        if not to or not message:
            logger.error("SMS send skipped: missing recipient or message body")
            return {"status": "failed", "error": "missing_recipient_or_message"}

        request = self._build_request(to, message)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(**request)
        except Exception as exc:
            logger.error(
                f"SMS send error via {self._provider}: {exc}", exc_info=True
            )
            return {"status": "failed", "error": str(exc)}

        if 200 <= response.status_code < 300:
            return {"status": "sent", "provider": self._provider}

        logger.error(
            f"SMS send failed via {self._provider} "
            f"(HTTP {response.status_code}): {response.text[:500]}"
        )
        return {
            "status": "failed",
            "error": f"http_{response.status_code}",
            "detail": response.text[:500],
        }

    def _build_request(self, to: str, message: str) -> dict[str, Any]:
        """Build the provider-specific httpx request kwargs."""
        if self._provider == "msg91":
            return {
                "method": "POST",
                "url": self._endpoint_url,
                "json": {
                    "authkey": self._api_key or "",
                    "mobiles": to,
                    "message": message,
                    "sender": self._sender_id or "INFALE",
                    "route": 4,
                },
            }
        if self._provider == "twilio":
            data: dict[str, str] = {"To": to, "Body": message}
            if self._sender_id:
                data["From"] = self._sender_id
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Basic {self._api_key}"
            return {
                "method": "POST",
                "url": self._endpoint_url,
                "data": data,
                "headers": headers,
            }
        # Generic JSON provider: {"to": ..., "message": ..., "sender": ...}
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return {
            "method": "POST",
            "url": self._endpoint_url,
            "json": {"to": to, "message": message, "sender": self._sender_id},
            "headers": headers,
        }
