"""TOTP-based MFA."""

from __future__ import annotations

import secrets
from typing import Optional

import pyotp


class MFAService:
    """TOTP-based MFA with recovery code generation."""

    def generate_mfa_secret(self) -> str:
        """Generate a TOTP secret.

        Returns:
            A base32-encoded TOTP secret.
        """
        return pyotp.random_base32()

    def verify_mfa_code(self, secret: str, code: str) -> bool:
        """Verify a TOTP code.

        Args:
            secret: The TOTP secret.
            code: The TOTP code to verify.

        Returns:
            True if the code is valid, False otherwise.
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)
        except Exception:
            return False

    def generate_recovery_codes(self, count: int = 10) -> list[str]:
        """Generate recovery codes for MFA.

        Args:
            count: Number of recovery codes to generate.

        Returns:
            List of recovery codes.
        """
        return [secrets.token_urlsafe(16) for _ in range(count)]

    def generate_provisioning_uri(
        self, secret: str, email: str, issuer_name: str = "Infalette"
    ) -> str:
        """Generate a provisioning URI for QR code.

        Args:
            secret: The TOTP secret.
            email: The user's email.
            issuer_name: The issuer name.

        Returns:
            A provisioning URI string.
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer_name)
