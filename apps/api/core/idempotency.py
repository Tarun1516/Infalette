"""Idempotency support for checkout/payment endpoints.

Uses Redis to store idempotency keys with TTL. If same key is reused,
returns the cached response instead of re-executing.

Fixes:
 - Robust path matching via startswith (not substring)
 - Captures actual response body after call_next for replay
 - Tenant scoping via AuthMiddleware context (ensures Auth runs before Idempotency)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Use prefixes with API version for robust matching
IDEMPOTENCY_PATH_PREFIXES = (
    "/api/v1/checkout",
    "/api/v1/orders",
    "/api/v1/payments",
    "/checkout",
    "/orders",
    "/payments",
)
IDEMPOTENCY_TTL_SECONDS = 24 * 3600  # 24h


def _is_idempotent_path(path: str) -> bool:
    """Robust check: path equals prefix or starts with prefix + '/'."""
    # Normalize - strip trailing slash for comparison, but also allow prefix match
    # e.g. /api/v1/checkout exact, /api/v1/checkout/123, /checkout etc.
    clean = path.rstrip("/") or "/"
    for prefix in IDEMPOTENCY_PATH_PREFIXES:
        p = prefix.rstrip("/") or "/"
        if clean == p or clean.startswith(p + "/"):
            return True
        # Also check without api prefix for flexibility
        if clean.startswith(p):
            # ensure not false positive like /ordershistory should not match /orders
            # The above startswith "/" ensures prefix boundary; fallback is strict
            if len(clean) == len(p) or clean[len(p)] == "/":
                return True
    return False


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis
                from infalette_config import get_settings

                settings = get_settings()
                self._redis = redis.from_url(settings.redis.url, decode_responses=True)
            except Exception:
                return None
        return self._redis

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Determine if idempotency applies
        is_post = request.method == "POST"
        is_path = _is_idempotent_path(request.url.path)
        has_key_header = "Idempotency-Key" in request.headers or "idempotency-key" in request.headers

        if not is_post:
            return await call_next(request)
        if not is_path and not has_key_header:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        if not idempotency_key:
            return await call_next(request)

        # Tenant scoping – AuthMiddleware should have run before us
        tenant_suffix = ""
        try:
            # AuthMiddleware stores tenant_context on request.state
            tc = getattr(request.state, "tenant_context", None)
            if tc is not None and hasattr(tc, "tenant_id") and tc.tenant_id:
                tenant_suffix = f":{tc.tenant_id}"
            else:
                # Fallback: try to extract from Authorization (user tenant)
                user = getattr(request.state, "user", None)
                if user and getattr(user, "tenant_id", None):
                    tenant_suffix = f":{user.tenant_id}"
                elif hasattr(request.state, "tenant_plan"):
                    tenant_suffix = f":{request.state.tenant_plan}"
        except Exception:
            pass

        # Hash key to avoid extremely long redis keys but keep tenant suffix
        hashed = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        cache_key = f"idempotency:{hashed}{tenant_suffix}"

        redis = await self._get_redis()
        if redis is None:
            return await call_next(request)

        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return Response(
                    content=json.dumps(data.get("body", {})),
                    status_code=data.get("status", 200),
                    headers={**data.get("headers", {}), "X-Idempotent-Replayed": "true"},
                    media_type="application/json",
                )
        except Exception as e:
            logger.debug("idempotency cache read failed: %s", e)

        response = await call_next(request)

        # Only cache 2xx responses – capture actual body
        if 200 <= response.status_code < 300:
            try:
                body_bytes = b""
                headers_dict = dict(response.headers)

                # Try to extract body from Response object
                # For JSONResponse / Response, body is available as attribute
                if hasattr(response, "body"):
                    try:
                        body_bytes = response.body  # type: ignore[attr-defined]
                    except Exception:
                        body_bytes = b""
                # For streaming, collect chunks
                if not body_bytes and hasattr(response, "body_iterator"):
                    chunks = []
                    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                        if isinstance(chunk, str):
                            chunk = chunk.encode()
                        chunks.append(chunk)
                    body_bytes = b"".join(chunks)
                    # Recreate response so downstream still has body
                    response = Response(
                        content=body_bytes,
                        status_code=response.status_code,
                        headers=headers_dict,
                        media_type=response.media_type,
                    )
                    # Need to re-set Idempotency header after recreation
                body_json: dict | list | str
                if body_bytes:
                    try:
                        body_json = json.loads(body_bytes.decode())
                    except Exception:
                        # Not JSON – store as text
                        body_json = body_bytes.decode(errors="ignore")
                else:
                    body_json = {}

                # Remove hop-by-hop headers before caching
                headers_to_cache = {k: v for k, v in headers_dict.items() if k.lower() not in ("content-length", "connection")}
                await redis.setex(
                    cache_key,
                    IDEMPOTENCY_TTL_SECONDS,
                    json.dumps({"status": response.status_code, "body": body_json, "headers": headers_to_cache}),
                )
            except Exception as e:
                logger.debug("idempotency cache write failed: %s", e)

        # Echo key
        try:
            response.headers["Idempotency-Key"] = idempotency_key
        except Exception:
            pass
        return response


async def check_idempotency_key(request: Request, redis) -> Optional[str]:
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None
    # hash to avoid extremely long keys
    return hashlib.sha256(key.encode()).hexdigest()
