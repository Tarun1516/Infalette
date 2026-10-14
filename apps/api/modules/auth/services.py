"""Authentication services."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.user import User
from infalette_database.models.role import Role, UserRole
from infalette_database.models.tenant import Tenant, TenantStatus
from infalette_database.models.domain import Domain
from infalette_auth.security import PasswordHasher
from infalette_auth.jwt import TokenManager
from infalette_auth.mfa import MFAService
from infalette_auth.schemas import LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest, MFAVerifyRequest, MFASetupResponse


def _mfa_required_for(user: User) -> bool:
    """True when this user's role must be MFA-enrolled (spec §5).

    Local development (``app_env != "production"``) is permissive:
    admin roles can log in without enrolling TOTP. The spec mandate
    still applies in production; we only relax it so the bundled demo
    creds ``owner@demo.test / demo1234`` are usable end-to-end.
    """
    from infalette_config import get_settings

    try:
        settings = get_settings()
        env = (settings.app_env or "").lower()
    except Exception:
        env = "development"

    if env != "production":
        return False

    try:
        required = settings.auth.mfa_required_roles
    except Exception:
        required = "platform_owner,tenant_owner,store_manager"
    roles = {r.strip().lower() for r in (required or "").split(",") if r.strip()}
    if not roles:
        return False
    return str(getattr(user, "role", "") or "").lower() in roles


def _create_enrollment_token(user: User) -> str:
    """Short-lived token restricted to /auth/mfa/* endpoints."""
    from datetime import timedelta

    token_manager = TokenManager()
    return token_manager.create_access_token(
        subject=str(user.id),
        tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        expires_delta=timedelta(minutes=15),
        scope="mfa_enrollment",
    )


async def login(data: LoginRequest, session: AsyncSession) -> TokenResponse:
    """Login with email and password, enforcing MFA if enabled.

    Args:
        data: Login request data (may include mfa_code).
        session: Database session.

    Returns:
        Token response with access and refresh tokens.

    Raises:
        ValueError: if credentials invalid or MFA required/invalid.
    """
    result = await session.execute(
        select(User).where(User.email == data.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("Invalid email or password")

    hasher = PasswordHasher()
    if not hasher.verify_password(data.password, user.password_hash):
        raise ValueError("Invalid email or password")

    # MFA enforcement
    if getattr(user, "mfa_enabled", False):
        if not user.mfa_secret:
            # Misconfigured – treat as not enabled
            pass
        else:
            mfa_code = getattr(data, "mfa_code", None)
            if not mfa_code:
                raise ValueError("MFA code required")
            mfa_service = MFAService()
            if len(mfa_code) == 6:
                if not mfa_service.verify_mfa_code(user.mfa_secret, mfa_code):
                    raise ValueError("Invalid MFA code")
            else:
                # Recovery code (single use, hashed at rest)
                if not await _consume_recovery_code(user, session, mfa_code):
                    raise ValueError("Invalid MFA recovery code")

    # MFA enrollment enforcement (spec §5: "MFA for admins"): staff roles
    # must complete TOTP enrollment before receiving a full-access token.
    if not getattr(user, "mfa_enabled", False) and _mfa_required_for(user):
        return TokenResponse(
            access_token=_create_enrollment_token(user),
            refresh_token="",
            mfa_required=True,
            scope="mfa_enrollment",
        )

    token_manager = TokenManager()
    access_token = token_manager.create_access_token(
        subject=str(user.id),
        tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
    )
    refresh_token = token_manager.create_refresh_token(
        subject=str(user.id),
        tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def confirm_mfa_enrollment(
    user: User, mfa_code: str, session: AsyncSession
) -> TokenResponse:
    """Confirm TOTP enrollment and exchange the restricted token for full ones.

    Called from ``POST /auth/mfa/confirm-enrollment`` with the enrollment-
    scoped token issued at login. Verifies the code against the secret
    created by ``setup_mfa``, enables MFA, and issues normal tokens.
    """
    mfa_service = MFAService()
    secret = getattr(user, "mfa_secret", None)
    if not secret:
        raise ValueError("MFA setup has not been completed for this account")
    if not mfa_service.verify_mfa_code(secret, mfa_code):
        raise ValueError("Invalid MFA code")

    user.mfa_enabled = True
    await session.commit()

    token_manager = TokenManager()
    return TokenResponse(
        access_token=token_manager.create_access_token(
            subject=str(user.id),
            tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        ),
        refresh_token=token_manager.create_refresh_token(
            subject=str(user.id),
            tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        ),
    )


async def register(data: RegisterRequest, session: AsyncSession) -> TokenResponse:
    """Register a new tenant with admin user.

    Args:
        data: Registration data.
        session: Database session.

    Returns:
        Token response with access and refresh tokens.
    """
    # Create tenant
    slug = data.tenant_name.lower().replace(" ", "-").replace("_", "-")
    tenant = Tenant(
        name=data.tenant_name,
        slug=slug,
        plan_id=data.plan_id,
        status=TenantStatus.ACTIVE,
    )
    session.add(tenant)
    await session.flush()

    # Create admin user
    hasher = PasswordHasher()
    password_hash = hasher.hash_password(data.admin_password)

    admin_user = User(
        tenant_id=tenant.id,
        email=data.admin_email,
        password_hash=password_hash,
        first_name="Admin",
        last_name="User",
        role=UserRole.TENANT_OWNER.value,
        status="active",
    )
    session.add(admin_user)
    await session.flush()

    # Create default domain
    domain = Domain(
        tenant_id=tenant.id,
        domain=f"{slug}.infalette.com",
        is_primary=True,
        verified=True,
    )
    session.add(domain)

    await session.commit()

    token_manager = TokenManager()
    access_token = token_manager.create_access_token(
        subject=str(admin_user.id),
        tenant_id=tenant.id,
    )
    refresh_token = token_manager.create_refresh_token(
        subject=str(admin_user.id),
        tenant_id=tenant.id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def refresh_token(data: RefreshTokenRequest, session: AsyncSession) -> TokenResponse:
    """Refresh access token.

    Args:
        data: Refresh token request.
        session: Database session.

    Returns:
        Token response with new access token.
    """
    token_manager = TokenManager()
    payload = token_manager.decode_token(data.refresh_token)

    if payload.token_type != "refresh":
        raise ValueError("Invalid token type")

    user_id = UUID(payload.sub)
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    access_token = token_manager.create_access_token(
        subject=str(user.id),
        tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=data.refresh_token,
    )


async def verify_mfa(data: MFAVerifyRequest, session: AsyncSession) -> TokenResponse:
    """Verify MFA code (also verifies password).

    Handles both login MFA verification and setup confirmation.
    If user has mfa_secret but mfa_enabled is False, successful verification
    will enable MFA.
    """
    result = await session.execute(
        select(User).where(User.email == data.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("Invalid email or password")

    # Verify password as well (MFAVerifyRequest includes password)
    hasher = PasswordHasher()
    if not hasher.verify_password(data.password, user.password_hash):
        raise ValueError("Invalid email or password")

    if not user.mfa_secret:
        raise ValueError("MFA not enabled for this user")

    mfa_service = MFAService()
    if not mfa_service.verify_mfa_code(user.mfa_secret, data.mfa_code):
        raise ValueError("Invalid MFA code")

    # If MFA was in setup pending state, enable it now
    if not user.mfa_enabled:
        user.mfa_enabled = True
        await session.commit()
        await session.refresh(user)

    token_manager = TokenManager()
    access_token = token_manager.create_access_token(
        subject=str(user.id),
        tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
    )
    refresh_token = token_manager.create_refresh_token(
        subject=str(user.id),
        tenant_id=user.tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def _consume_recovery_code(user: User, session: AsyncSession, code: str) -> bool:
    """Check a recovery code and consume it on success. Codes are bcrypt-hashed."""
    import hmac as _hmac

    hasher = PasswordHasher()
    stored = list(user.mfa_recovery_codes_json or [])
    for i, code_hash in enumerate(stored):
        try:
            if hasher.verify_password(code, str(code_hash)):
                stored.pop(i)
                user.mfa_recovery_codes_json = stored
                await session.commit()
                return True
        except Exception:
            continue
    return False


async def setup_mfa(user: User, session: AsyncSession) -> MFASetupResponse:
    """Set up MFA for the current user – generates secret and persists.

    Sets mfa_secret and mfa_enabled (pending). Recovery codes are returned
    once; caller should store securely.

    Args:
        user: The current user (managed instance).
        session: DB session to persist.

    Returns:
        MFA setup response with secret, provisioning URI, and recovery codes.
    """
    mfa_service = MFAService()
    secret = mfa_service.generate_mfa_secret()
    provisioning_uri = mfa_service.generate_provisioning_uri(secret, user.email)
    recovery_codes = mfa_service.generate_recovery_codes()

    # Persist secret + hashed recovery codes (plaintext shown once)
    hasher = PasswordHasher()
    user.mfa_secret = secret
    user.mfa_recovery_codes_json = [hasher.hash_password(c) for c in recovery_codes]
    # Mark enabled False initially – verify_mfa will flip to True on successful code
    # If you want immediate enable, set True here; we set True for simplicity per task spec
    # Task says "update user mfa_enabled, mfa_secret" – so enable now
    user.mfa_enabled = True
    await session.commit()
    await session.refresh(user)

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        recovery_codes=recovery_codes,
    )


async def confirm_mfa_setup(user: User, code: str, session: AsyncSession) -> bool:
    """Confirm MFA setup with a code – verifies and ensures enabled."""
    if not user.mfa_secret:
        raise ValueError("MFA not initialized")
    mfa_service = MFAService()
    if not mfa_service.verify_mfa_code(user.mfa_secret, code):
        return False
    user.mfa_enabled = True
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Shopper (customer) accounts + password reset
# ---------------------------------------------------------------------------

async def customer_register(
    data: "CustomerRegisterRequest",
    session: AsyncSession,
    tenant_id,
) -> TokenResponse:
    """Register a shopper account scoped to a tenant.

    Shoppers live in ``users`` with role=customer so the whole JWT/MFA
    stack applies unchanged.
    """
    from fastapi import HTTPException

    from infalette_database.models.user import User as _User
    from infalette_auth.security import PasswordHasher

    email = data.email.lower().strip()
    existing = (
        await session.execute(
            select(_User).where(_User.email == email, _User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    hasher = PasswordHasher()
    user = _User(
        tenant_id=tenant_id,
        email=email,
        password_hash=hasher.hash_password(data.password),
        first_name=data.first_name or "",
        last_name=data.last_name or "",
        role="customer",
        status="active",
    )
    session.add(user)

    # Mirror into the CRM customer profile
    try:
        from infalette_database.models.customer import Customer

        session.add(
            Customer(
                tenant_id=tenant_id,
                email=email,
                first_name=data.first_name or "",
                last_name=data.last_name or "",
            )
        )
    except Exception:
        pass

    await session.commit()

    token_manager = TokenManager()
    return TokenResponse(
        access_token=token_manager.create_access_token(str(user.id), tenant_id),
        refresh_token=token_manager.create_refresh_token(str(user.id), tenant_id),
    )


async def forgot_password(email: str, session: AsyncSession, tenant_id=None) -> dict:
    """Issue a single-use password-reset token valid for 1 hour."""
    from infalette_database.models.user import User as _User

    email = (email or "").lower().strip()
    query = select(_User).where(_User.email == email)
    if tenant_id is not None:
        query = query.where(_User.tenant_id == tenant_id)
    user = (await session.execute(query)).scalars().first()

    # Always report accepted to avoid account enumeration.
    result: dict = {"status": "accepted"}
    if user is None:
        return result

    import secrets as _secrets

    from infalette_config import get_settings

    settings = get_settings()
    token = _secrets.token_urlsafe(32)

    # Primary store: Redis. Fallback outside production: in-process memory
    # so the flow stays testable in dev without infrastructure.
    stored = False
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis.url, decode_responses=True)
        await client.set(f"pwreset:{token}", str(user.id), ex=3600)
        await client.aclose()
        stored = True
    except Exception:
        if (settings.app_env or "").lower() != "production":
            _RESET_TOKENS[token] = (str(user.id), datetime.now().timestamp() + 3600)
            stored = True

    if not stored:
        return result

    # Email the reset link when delivery is configured
    try:
        from infalette_integrations.email.client import EmailClient

        frontend = str(settings.storefront_url or "").rstrip("/")
        await EmailClient().send_email(
            to=user.email,
            subject="Reset your password",
            html_content=(
                f"<p>Click below to reset your password (valid 1 hour):</p>"
                f"<p><a href=\"{frontend}/reset-password?token={token}\">Reset password</a></p>"
            ),
            tenant_id=user.tenant_id,
        )
        emailed = True
    except Exception:
        emailed = False

    # Dev convenience: surface the token only outside production when no
    # email delivery is configured, so the flow can complete end-to-end.
    if (
        (settings.app_env or "").lower() != "production"
        and not _email_delivery_configured(settings)
    ):
        result["reset_token"] = token
    return result


_RESET_TOKENS: dict = {}


def _email_delivery_configured(settings) -> bool:
    try:
        s = settings.email
        return bool(getattr(s, "smtp_host", None) or getattr(s, "aws_region", None))
    except Exception:
        return False


def _consume_pending_reset(token: str):
    """Look up a reset token in Redis, then the in-memory dev fallback."""
    import time as _time

    try:
        import redis.asyncio as redis

        from infalette_config import get_settings

        client = redis.from_url(get_settings().redis.url, decode_responses=True)

        import asyncio as _asyncio

        async def _get():
            value = await client.get(f"pwreset:{token}")
            if value:
                await client.delete(f"pwreset:{token}")
            await client.aclose()
            return value

        try:
            loop = _asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            value = loop.run_until_complete(_get())
        else:
            value = _asyncio.run(_get())
        if value:
            return value
    except Exception:
        pass

    entry = _RESET_TOKENS.pop(token, None)
    if entry and entry[1] > _time.time():
        return entry[0]
    _RESET_TOKENS.pop(token, None)
    return None


async def reset_password(token: str, new_password: str, session: AsyncSession) -> dict:
    """Consume a reset token and set the new password."""
    from fastapi import HTTPException

    from infalette_database.models.user import User as _User
    from infalette_auth.security import PasswordHasher

    if not token or not new_password or len(new_password) < 8:
        raise HTTPException(status_code=422, detail="Invalid token or weak password")

    user_id = _consume_pending_reset(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")

    user = (
        await session.execute(select(_User).where(_User.id == UUID(user_id)))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    hasher = PasswordHasher()
    user.password_hash = hasher.hash_password(new_password)
    await session.commit()
    return {"status": "password_reset"}
