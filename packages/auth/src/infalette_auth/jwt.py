"""JWT token management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from jose import jwt, JWTError

from infalette_config import get_settings


class TokenPayload:
    """JWT token payload."""

    def __init__(
        self,
        sub: str,
        tenant_id: str,
        exp: int,
        token_type: str,
        scope: Optional[str] = None,
    ) -> None:
        self.sub = sub
        self.tenant_id = tenant_id
        self.exp = exp
        self.token_type = token_type
        self.scope = scope


class TokenManager:
    """JWT token creation, validation, and refresh."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def create_access_token(
        self,
        subject: str,
        tenant_id: UUID,
        expires_delta: Optional[timedelta] = None,
        scope: Optional[str] = None,
    ) -> str:
        """Create a JWT access token.

        Args:
            subject: The subject (user ID) of the token.
            tenant_id: The tenant ID associated with the token.
            expires_delta: Optional expiration time override.
            scope: Optional scope restriction (e.g. ``mfa_enrollment``).
                Tokens with a restricted scope are rejected everywhere
                except the allowed endpoints.

        Returns:
            The JWT access token as a string.
        """
        if expires_delta is None:
            expires_delta = timedelta(
                minutes=self._settings.auth.access_token_expire_minutes
            )

        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {
            "sub": str(subject),
            "tenant_id": str(tenant_id),
            "exp": expire,
            "type": "access",
            "iat": datetime.now(timezone.utc),
        }
        if scope:
            to_encode["scope"] = scope
        secret = self._settings.auth.secret_key.get_secret_value()
        return jwt.encode(to_encode, secret, algorithm=self._settings.auth.jwt_algorithm)

    def create_refresh_token(
        self,
        subject: str,
        tenant_id: UUID,
    ) -> str:
        """Create a JWT refresh token.

        Args:
            subject: The subject (user ID) of the token.
            tenant_id: The tenant ID associated with the token.

        Returns:
            The JWT refresh token as a string.
        """
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._settings.auth.refresh_token_expire_days
        )
        to_encode = {
            "sub": str(subject),
            "tenant_id": str(tenant_id),
            "exp": expire,
            "type": "refresh",
            "iat": datetime.now(timezone.utc),
        }
        secret = self._settings.auth.secret_key.get_secret_value()
        return jwt.encode(to_encode, secret, algorithm=self._settings.auth.jwt_algorithm)

    def decode_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT token.

        Args:
            token: The JWT token to decode.

        Returns:
            The token payload.

        Raises:
            JWTError: If the token is invalid or expired.
        """
        secret = self._settings.auth.secret_key.get_secret_value()
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[self._settings.auth.jwt_algorithm],
            )
        except JWTError as e:
            raise JWTError(f"Invalid token: {e}") from e

        return TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            exp=payload["exp"],
            token_type=payload["type"],
            scope=payload.get("scope"),
        )

    def verify_token(self, token: str) -> bool:
        """Verify that a token is valid.

        Args:
            token: The JWT token to verify.

        Returns:
            True if the token is valid, False otherwise.
        """
        try:
            self.decode_token(token)
            return True
        except JWTError:
            return False
