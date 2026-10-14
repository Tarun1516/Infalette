"""PostHog product analytics client."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from infalette_config import get_settings

logger = logging.getLogger(__name__)


class PosthogClient:
    """Fire-and-forget PostHog capture client; never raises.

    Disabled unless ``settings.posthog.enabled`` is true and an API key is
    configured, so dev/test environments stay offline-safe.
    """

    def __init__(self) -> None:
        self._settings = get_settings().posthog

    def capture(
        self,
        event: str,
        distinct_id: str,
        properties: Optional[dict] = None,
    ) -> Optional[dict]:
        """Capture a single event to PostHog (sync, short timeout)."""
        if not self._settings.enabled or not self._settings.api_key:
            return None

        url = f"{(self._settings.host or '').rstrip('/')}/capture/"
        body = {
            "api_key": self._settings.api_key,
            "event": event,
            "distinct_id": distinct_id,
            "properties": dict(properties or {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            response = httpx.post(url, json=body, timeout=2)
            logger.debug(
                f"PostHog capture '{event}' -> HTTP {response.status_code}"
            )
            return {"status_code": response.status_code}
        except Exception as exc:  # never break caller on analytics failure
            logger.debug(f"PostHog capture failed for '{event}': {exc}")
            return None
