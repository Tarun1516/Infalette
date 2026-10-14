"""Clerk session-token verification for the FastAPI backend.

Clerk issues RS256 session JWTs signed by the app's JWKS endpoint.
The frontend sends them as ``Authorization: Bearer <clerk-jwt>``; this
module verifies the signature and maps the claims to a local user.

Contract:
- ``verify_clerk_token`` returns the decoded claims (raises on failure).
- ``resolve_jwks_url`` prefers ``CLERK_JWKS_URL``, else derives
  ``https://<domain>/.well-known/jwks.json`` from
  ``CLERK_PUBLISHABLE_KEY`` (format ``pk_..._<base64-domain>`` is NOT
  reliable, so we also accept ``CLERK_DOMAIN`` env as fallback).
- JWKS keys are cached in-memory for 10 minutes to avoid a fetch per request.
- When Clerk is not configured, all helpers raise/return clearly so the
  legacy HS256 path in dependencies.py keeps working untouched.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_JWKS_CACHE: dict[str, Any] = {"keys": None, "ts": 0.0, "url": None}
_JWKS_TTL_S = 600.0


def _get_settings():
    from infalette_config import get_settings

    return get_settings()


def resolve_jwks_url() -> str | None:
    """Return the JWKS URL or None when Clerk is not configured."""
    import os

    settings = _get_settings()
    clerk = getattr(settings, "clerk", None)
    if clerk is not None and getattr(clerk, "jwks_url", None):
        return clerk.jwks_url
    env_url = os.environ.get("CLERK_JWKS_URL")
    if env_url:
        return env_url
    domain = os.environ.get("CLERK_DOMAIN")
    if not domain and clerk is not None:
        # Try to derive from the publishable key's embedded API URL hint?
        # Clerk publishable keys do not reliably embed the domain, so we
        # require explicit config instead of guessing.
        pass
    if domain:
        domain = domain.rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/.well-known/jwks.json"
    return None


def _fetch_jwks(url: str) -> dict:
    """Fetch JWKS JSON, cached for _JWKS_TTL_S."""
    import httpx

    now = time.time()
    if (
        _JWKS_CACHE["keys"] is not None
        and _JWKS_CACHE["url"] == url
        and now - _JWKS_CACHE["ts"] < _JWKS_TTL_S
    ):
        return _JWKS_CACHE["keys"]

    resp = httpx.get(url, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    _JWKS_CACHE.update({"keys": data, "ts": now, "url": url})
    return data


def _find_jwk(jwks: dict, kid: str | None) -> dict | None:
    for k in jwks.get("keys", []):
        if kid is None or k.get("kid") == kid:
            return k
    return None


def verify_clerk_token(token: str) -> dict[str, Any]:
    """Verify a Clerk session JWT and return its claims.

    Raises:
        RuntimeError: when Clerk is not configured (no JWKS URL).
        ValueError: when the token is invalid/expired.
    """
    from jose import jwt as jose_jwt
    from jose.utils import base64url_decode

    jwks_url = resolve_jwks_url()
    if not jwks_url:
        raise RuntimeError(
            "Clerk is not configured: set CLERK_JWKS_URL (or CLERK_DOMAIN) "
            "and CLERK_SECRET_KEY/CLERK_PUBLISHABLE_KEY"
        )

    import json

    try:
        header_b64 = token.split(".")[0]
        padded = header_b64 + "=" * (-len(header_b64) % 4)
        header = json.loads(base64url_decode(padded.encode()).decode())
    except Exception as e:
        raise ValueError(f"Malformed Clerk token: {e}") from e

    kid = header.get("kid")
    try:
        jwks = _fetch_jwks(jwks_url)
    except Exception as e:
        raise ValueError(f"Could not fetch Clerk JWKS: {e}") from e

    jwk = _find_jwk(jwks, kid)
    if not jwk:
        # Force-refresh once in case of key rotation.
        _JWKS_CACHE.update({"keys": None, "ts": 0.0, "url": None})
        try:
            jwks = _fetch_jwks(jwks_url)
        except Exception as e:
            raise ValueError(f"Could not refresh Clerk JWKS: {e}") from e
        jwk = _find_jwk(jwks, kid)
    if not jwk:
        raise ValueError("Clerk JWKS has no matching key (kid mismatch)")

    try:
        claims = jose_jwt.decode(
            token,
            jwk,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except Exception as e:
        raise ValueError(f"Invalid Clerk token: {e}") from e

    if "sub" not in claims:
        raise ValueError("Clerk token has no sub claim")
    return claims


def claims_to_user_fields(claims: dict[str, Any]) -> dict[str, Any]:
    """Map Clerk claims to local user fields for lookup/creation."""
    email = (
        claims.get("email")
        or (claims.get("email_addresses") or [None])[0]
        if isinstance(claims.get("email_addresses"), list)
        else claims.get("email")
    )
    return {
        "clerk_user_id": claims.get("sub"),
        "email": email,
        "first_name": claims.get("given_name") or claims.get("first_name"),
        "last_name": claims.get("family_name") or claims.get("last_name"),
    }
