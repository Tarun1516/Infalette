"""Custom middleware for the API."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware adding a per-request ID (X-Request-ID) and timing."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        import uuid as uuid_mod

        start_time = time.time()
        request_id = request.headers.get("X-Request-ID") or uuid_mod.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis sliding window."""

    def __init__(self, app: ASGIApp, requests_per_minute: int = 60) -> None:
        super().__init__(app)
        self._requests_per_minute = requests_per_minute
        self._redis = None

    async def _get_redis(self):
        """Get Redis connection lazily."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                from infalette_config import get_settings
                settings = get_settings()
                self._redis = redis.from_url(settings.redis.url, decode_responses=True)
            except Exception:
                return None
        return self._redis

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and webhooks
        path = request.url.path
        if path in ("/health", "/healthz", "/ready") or path.startswith(("/webhooks/", "/api/v1/webhooks/")):
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"rate_limit:{client_ip}:{path}"

        redis = await self._get_redis()
        if redis is None:
            # Redis unavailable: fail open by default (availability first),
            # or fail closed for strict deployments (RATE_LIMIT_FAIL_CLOSED=true)
            from infalette_config import get_settings as _gs

            try:
                fail_closed = bool(getattr(_gs(), "rate_limit_fail_closed", False))
            except Exception:
                fail_closed = False
            if fail_closed:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=503,
                    content={"detail": "Rate limiter unavailable, retry shortly."},
                    headers={"Retry-After": "10"},
                )
            return await call_next(request)

        try:
            # Sliding window rate limiting
            now = time.time()
            window_start = now - 60  # 1 minute window

            # Remove old entries
            await redis.zremrangebyscore(rate_key, 0, window_start)

            # Count current requests
            count = await redis.zcard(rate_key)

            if count >= self._requests_per_minute:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again in a minute."},
                    headers={"Retry-After": "60"},
                )

            # Add current request
            await redis.zadd(rate_key, {str(now): now})
            # Set expiry on the key
            await redis.expire(rate_key, 60)
        except Exception:
            # If Redis fails, allow the request through
            pass

        return await call_next(request)
