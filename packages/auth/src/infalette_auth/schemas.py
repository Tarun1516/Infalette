"""Auth-related Pydantic schemas."""

from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# Lightweight RFC-5321-ish email check. Pydantic's bundled ``EmailStr``
# uses the ``email-validator`` package which rejects reserved/special-
# use TLDs (``.test``, ``.example``, ``.invalid``). We accept them on
# the auth surface so the local demo creds ``owner@demo.test`` work
# out of the box without standing up a real domain.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value or ""))


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # MFA enrollment flow: when True the access token is a restricted
    # enrollment token valid only for /auth/mfa/* endpoints.
    mfa_required: bool = False
    scope: Optional[str] = None


class MFAConfirmRequest(BaseModel):
    """Confirm MFA enrollment with a TOTP code (enrollment-token auth)."""

    mfa_code: str = Field(..., min_length=6, max_length=6)


def _validate_email(value: str) -> str:
    if not _is_email(value):
        raise ValueError("invalid email address")
    return value


class LoginRequest(BaseModel):
    """Login request schema."""

    email: str
    password: str
    mfa_code: Optional[str] = Field(default=None, min_length=6, max_length=6, description="TOTP code if MFA enabled")

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_email(v)


class RegisterRequest(BaseModel):
    """Register request schema."""

    tenant_name: str = Field(..., min_length=1, max_length=255)
    admin_email: str
    admin_password: str = Field(..., min_length=8)
    plan_id: UUID

    @field_validator("admin_email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_email(v)


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class MFAVerifyRequest(BaseModel):
    """MFA verification request schema."""

    email: str
    password: str
    mfa_code: str = Field(..., min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_email(v)


class MFASetupResponse(BaseModel):
    """MFA setup response schema."""

    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class UserRead(BaseModel):
    """User read schema."""

    model_config = {"from_attributes": True}

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    mfa_enabled: bool
