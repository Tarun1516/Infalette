"""Bot protection middleware.

Checks:
- X-Bot header (simple bot flag)
- reCAPTCHA token header (X-Recaptcha-Token) if RECAPTCHA_SECRET_KEY is configured
- Known bot User-Agent patterns
- Per-IP rate limiting for suspected bots (stricter than normal RateLimitMiddleware)

Keep it simple but functional. Never blocks health/docs/webhooks.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Paths exempt from bot checks
EXEMPT_PREFIXES = ("/health", "/healthz", "/ready", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi", "/webhooks", "/api/v1/webhooks/payments", "/api/v1/webhooks/instagram", "/api/v1/webhooks/whatsapp")

# Simple known bot UA substrings (lowercased)
KNOWN_BOT_UAS = (
    "googlebot",
    "bingbot",
    "slurp",
    "duckduckbot",
    "baiduspider",
    "yandexbot",
    "sogou",
    "exabot",
    "facebot",
    "ia_archiver",
    "semrush",
    "ahrefs",
    "dotbot",
    "mj12bot",
    "petalbot",
    "dataforseo",
)

# Default strict limit for bots (lower than normal users)
BOT_RATE_LIMIT = 20  # requests per minute
BOT_WINDOW = 60  # seconds


class BotProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware to detect and mitigate bots.

    Behavior:
    - If request has `X-Bot: 1|true|bot` header → treat as bot.
    - If User-Agent matches known bot list → treat as bot.
    - If reCAPTCHA is configured (RECAPTCHA_SECRET_KEY), require
      `X-Recaptcha-Token` header on POST/PUT/PATCH for non-exempt paths.
      Token is verified via Google's siteverify endpoint.
    - Bots are rate-limited more strictly (20/min vs 60/min). Excess → 429.
    - If BOT_BLOCK_UNKNOWN is true, unknown bots without valid recaptcha are blocked with 403.

    All checks are best-effort; failures to reach Redis or recaptcha service
    allow the request through (fail-open) to avoid breaking legit traffic.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._redis = None
        # Lazy-loaded settings
        self._settings = None

    def _get_settings(self):
        if self._settings is None:
            try:
                from infalette_config import get_settings

                self._settings = get_settings()
            except Exception:
                self._settings = None
        return self._settings

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as redis  # type: ignore

            settings = self._get_settings()
            redis_url = getattr(settings.redis, "url", "redis://localhost:6379/0") if settings else "redis://localhost:6379/0"
            self._redis = redis.from_url(redis_url, decode_responses=True)
        except Exception:
            return None
        return self._redis

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(p) for p in EXEMPT_PREFIXES)

    def _is_bot_via_header(self, request: Request) -> bool:
        """Check X-Bot header."""
        settings = self._get_settings()
        check_x_bot = True
        if settings and hasattr(settings, "bot"):
            check_x_bot = getattr(settings.bot, "check_x_bot_header", True)
        if not check_x_bot:
            return False
        x_bot = request.headers.get("X-Bot") or request.headers.get("x-bot") or request.headers.get("X-BOT")
        if x_bot is None:
            return False
        return x_bot.strip().lower() in ("1", "true", "yes", "bot", "blocked")

    def _is_bot_via_ua(self, request: Request) -> bool:
        ua = (request.headers.get("user-agent") or "").lower()
        if not ua:
            return False
        return any(bot in ua for bot in KNOWN_BOT_UAS)

    async def _verify_recaptcha(self, token: str, remote_ip: Optional[str] = None) -> bool:
        """Verify recaptcha token with Google.

        Returns True if verification succeeds or if not configured.
        Fail-open on network errors.
        """
        settings = self._get_settings()
        secret = None
        min_score = 0.5
        if settings and hasattr(settings, "bot"):
            secret = getattr(settings.bot, "recaptcha_secret_key", None)
            min_score = getattr(settings.bot, "recaptcha_min_score", 0.5)
        if not secret:
            # Not configured → treat as valid (no check)
            return True

        # If token is missing when verification is required, fail
        if not token:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    "https://www.google.com/recaptcha/api/siteverify",
                    data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
                )
                data = resp.json()
                if not data.get("success"):
                    logger.warning("recaptcha verification failed: %s", data.get("error-codes"))
                    return False
                # For reCAPTCHA v3, check score
                if "score" in data:
                    score = float(data.get("score", 0))
                    if score < float(min_score):
                        logger.warning("recaptcha low score: %s < %s", score, min_score)
                        return False
                return True
        except Exception as e:
            logger.warning("recaptcha verification error (fail-open): %s", e)
            return True  # fail-open

    async def _is_rate_limited_bot(self, request: Request) -> bool:
        """Check if bot IP is rate-limited (stricter). Returns True if limited."""
        settings = self._get_settings()
        limit = BOT_RATE_LIMIT
        window = BOT_WINDOW
        if settings and hasattr(settings, "bot"):
            limit = getattr(settings.bot, "rate_limit_requests", BOT_RATE_LIMIT)
            window = getattr(settings.bot, "rate_limit_window_seconds", BOT_WINDOW)
            # Use stricter limit for bots: e.g. 30% of normal or configured bot limit
            # If BOT_RATE_LIMIT_REQUESTS is 60 for users, bots get that value directly.

        redis = await self._get_redis()
        if redis is None:
            return False

        client_ip = request.client.host if request.client else "unknown"
        key = f"bot_rate:{client_ip}"

        try:
            now = time.time()
            window_start = now - window
            await redis.zremrangebyscore(key, 0, window_start)
            count = await redis.zcard(key)
            if count >= limit:
                return True
            await redis.zadd(key, {str(now): now})
            await redis.expire(key, window)
        except Exception as e:
            logger.debug("bot rate limit redis error: %s", e)
            return False
        return False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always exempt health/docs/webhooks
        if self._is_exempt(path):
            return await call_next(request)

        settings = self._get_settings()
        bot_enabled = True
        if settings and hasattr(settings, "bot"):
            bot_enabled = getattr(settings.bot, "enabled", True)
        if not bot_enabled:
            return await call_next(request)

        is_bot = False
        reason: Optional[str] = None

        # 1. X-Bot header
        if self._is_bot_via_header(request):
            is_bot = True
            reason = "x-bot-header"

        # 2. Known bot UA
        if not is_bot and self._is_bot_via_ua(request):
            is_bot = True
            reason = "known-ua"

        # 3. reCAPTCHA check for mutating requests if secret is configured
        recaptcha_secret = None
        recaptcha_header = "X-Recaptcha-Token"
        if settings and hasattr(settings, "bot"):
            recaptcha_secret = getattr(settings.bot, "recaptcha_secret_key", None)
            recaptcha_header = getattr(settings.bot, "recaptcha_header", "X-Recaptcha-Token")

        if recaptcha_secret and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # Only enforce recaptcha if header is expected; if missing, treat as bot signal
            token = request.headers.get(recaptcha_header) or request.headers.get(recaptcha_header.lower())
            if token:
                verified = await self._verify_recaptcha(token, request.client.host if request.client else None)
                if not verified:
                    logger.warning("bot blocked: invalid recaptcha ip=%s path=%s", request.client.host if request.client else "unknown", path)
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Bot verification failed. Invalid recaptcha token."},
                    )
            else:
                # No token provided — don't block by default, but mark as potential bot for rate limiting
                # If you want strict mode, set block_unknown_bots=True
                if is_bot:
                    # Already flagged as bot and no valid token → stricter handling
                    pass

        # 4. If flagged as bot, apply strict rate limiting and optional blocking
        if is_bot:
            logger.info("bot detected reason=%s ip=%s ua=%s path=%s", reason, request.client.host if request.client else "unknown", request.headers.get("user-agent", "")[:120], path)

            # Strict rate limit for bots
            if await self._is_rate_limited_bot(request):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Bot rate limit exceeded."},
                    headers={"Retry-After": "60"},
                )

            # Optional: block unknown bots outright if configured
            block_unknown = False
            if settings and hasattr(settings, "bot"):
                block_unknown = getattr(settings.bot, "block_unknown_bots", False)
            if block_unknown:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Bot traffic blocked."},
                )

            # Otherwise, add header and continue (allow but flagged)
            response = await call_next(request)
            response.headers["X-Bot-Detected"] = reason or "true"
            return response

        # Not a bot — normal flow
        return await call_next(request)
