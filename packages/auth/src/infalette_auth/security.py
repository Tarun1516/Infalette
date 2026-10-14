"""Password hashing and security utilities."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import bcrypt
from jose import jwt

from infalette_config import get_settings


class PasswordHasher:
    """Password hashing using bcrypt with configurable rounds."""

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: The plaintext password to hash.

        Returns:
            The hashed password as a string.
        """
        salt = bcrypt.gensalt(rounds=self._rounds)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a hash.

        Args:
            password: The plaintext password to verify.
            password_hash: The hashed password to compare against.

        Returns:
            True if the password matches the hash, False otherwise.
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False

    def generate_recovery_codes(self, count: int = 10) -> list[str]:
        """Generate recovery codes for MFA.

        Args:
            count: Number of recovery codes to generate.

        Returns:
            List of recovery codes.
        """
        return [secrets.token_urlsafe(16) for _ in range(count)]
