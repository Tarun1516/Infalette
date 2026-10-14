"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.schemas import LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest, MFAVerifyRequest, MFASetupResponse, MFAConfirmRequest, UserRead
from infalette_auth.dependencies import get_current_user

router = APIRouter()


class CustomerRegisterRequest(BaseModel):
    """Shopper signup (tenant-scoped customer account)."""

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8)
    first_name: str | None = None
    last_name: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Login with email and password."""
    from apps.api.modules.auth.services import login
    return await login(data, session)


@router.post("/register", response_model=TokenResponse)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Register a new tenant with admin user."""
    from apps.api.modules.auth.services import register
    return await register(data, session)


@router.post("/customer/register", response_model=TokenResponse)
async def customer_register(
    data: CustomerRegisterRequest,
    x_tenant: str = Header(default=None, alias="X-Tenant"),
    session: AsyncSession = Depends(get_async_session),
):
    """Shopper signup — creates a customer account for the tenant."""
    from fastapi import HTTPException as _HTTPException
    from sqlalchemy import select as _select
    from uuid import UUID as _UUID

    from infalette_database.models.tenant import Tenant as _Tenant
    from apps.api.modules.auth.services import customer_register as _svc

    if not x_tenant:
        raise _HTTPException(status_code=401, detail="Tenant required: send X-Tenant header")
    try:
        tenant_uuid = _UUID(x_tenant)
        tenant_id = tenant_uuid
    except ValueError:
        row = (
            await session.execute(_select(_Tenant).where(_Tenant.slug == x_tenant))
        ).scalar_one_or_none()
        if not row:
            raise _HTTPException(status_code=404, detail="Tenant not found")
        tenant_id = row.id
    return await _svc(data, session, tenant_id)


class _PasswordResetStatus(BaseModel):
    status: str
    reset_token: str | None = None


@router.post("/forgot-password", response_model=_PasswordResetStatus)
async def forgot_password(
    data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Issue a password-reset token (emailed; token echoed only in non-prod dev)."""
    from apps.api.modules.auth.services import forgot_password as _svc
    return await _svc(data.email, session)


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Consume a reset token and set a new password."""
    from apps.api.modules.auth.services import reset_password as _svc
    return await _svc(data.token, data.new_password, session)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Refresh access token."""
    from apps.api.modules.auth.services import refresh_token
    return await refresh_token(data, session)


@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(
    data: MFAVerifyRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Verify MFA code."""
    from apps.api.modules.auth.services import verify_mfa
    return await verify_mfa(data, session)


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Set up MFA for the current user – generates secret and enables MFA."""
    from apps.api.modules.auth.services import setup_mfa as svc_setup_mfa
    return await svc_setup_mfa(user, session)


@router.post("/mfa/confirm")
async def confirm_mfa(
    mfa_code: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Confirm MFA setup with a TOTP code."""
    from apps.api.modules.auth.services import confirm_mfa_setup
    ok = await confirm_mfa_setup(user, mfa_code, session)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    return {"status": "mfa_enabled"}


@router.post("/mfa/confirm-enrollment", response_model=TokenResponse)
async def confirm_mfa_enrollment(
    data: MFAConfirmRequest,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Complete mandatory MFA enrollment and receive full-access tokens.

    Used by admin roles whose login returned ``mfa_required=true`` with an
    enrollment-scoped token (spec §5: MFA for admins). Call
    ``POST /auth/mfa/setup`` first, then confirm the TOTP code here.
    """
    from apps.api.modules.auth.services import confirm_mfa_enrollment as svc

    try:
        return await svc(user, data.mfa_code, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    user=Depends(get_current_user),
):
    """Get current user info."""
    return user


@router.get("/users")
async def list_tenant_users(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List the tenant's team members (tenant owner / managers only)."""
    from fastapi import HTTPException as _HTTPException
    from sqlalchemy import select as _select

    from infalette_database.models.user import User as _User

    role_value = getattr(user.role, "value", str(user.role or ""))
    if role_value not in ("tenant_owner", "store_manager", "platform_owner", "admin"):
        raise _HTTPException(status_code=403, detail="Not authorized")

    result = await session.execute(
        _select(_User).where(_User.tenant_id == user.tenant_id)
    )
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": getattr(u.role, "value", u.role),
            "status": u.status,
            "mfa_enabled": bool(u.mfa_enabled),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in result.scalars().all()
    ]


@router.post("/users", status_code=201)
async def create_tenant_user(
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new team member inside the caller's tenant.

    Body fields:
        email            (required, unique)
        first_name       (required)
        last_name        (required)
        role             (required, one of: tenant_owner, store_manager,
                          platform_owner, admin, customer)
        password         (required, min 8 chars)
        mfa_required     (bool, default false). When true, the user is
                          created with ``mfa_enabled=False`` and a one-time
                          enrollment challenge is required on first login.
                          Admin role always forces ``mfa_required=True``
                          because admins are required to enroll MFA before
                          they can access admin surfaces.
        status           (one of: active, invited, suspended; default active)
    """
    from fastapi import HTTPException as _HTTPException
    from sqlalchemy import select as _select

    from infalette_auth.security import PasswordHasher
    from infalette_database.models.user import User as _User
    from infalette_database.models.user import UserStatus as _UserStatus

    caller_role = getattr(user.role, "value", str(user.role or ""))
    if caller_role not in ("tenant_owner", "store_manager", "platform_owner", "admin"):
        raise _HTTPException(status_code=403, detail="Not authorized to add team members")

    email = str(payload.get("email") or "").strip().lower()
    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    role = str(payload.get("role") or "").strip()
    password = str(payload.get("password") or "")

    if not email or not first_name or not last_name or not role or not password:
        raise _HTTPException(status_code=422, detail="email, first_name, last_name, role and password are required")
    if len(password) < 8:
        raise _HTTPException(status_code=422, detail="Password must be at least 8 characters")
    valid_roles = ("tenant_owner", "store_manager", "platform_owner", "admin", "customer")
    if role not in valid_roles:
        raise _HTTPException(status_code=422, detail=f"role must be one of {valid_roles}")

    # Admin accounts MUST have MFA enabled. We refuse to create the user
    # without it; the caller must tick the MFA box and we'll mark
    # mfa_enabled=False at create time and force enrollment on first
    # login (the login service already returns mfa_required=true when
    # the user has role=admin and mfa_enabled=false).
    mfa_required = bool(payload.get("mfa_required", role == "admin"))
    if role == "admin" and not mfa_required:
        raise _HTTPException(
            status_code=422,
            detail="Admins must have MFA enabled. Tick the MFA box to confirm.",
        )

    # Uniqueness: the user table has a global unique constraint on email
    existing = (await session.execute(_select(_User).where(_User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise _HTTPException(status_code=409, detail="A user with that email already exists")

    status_value = str(payload.get("status") or "active")
    if status_value not in ("active", "invited", "suspended"):
        status_value = "active"

    new_user = _User(
        tenant_id=user.tenant_id,
        email=email,
        password_hash=PasswordHasher().hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=role,
        mfa_enabled=False,
        # When MFA is required at creation time, we leave the user in
        # ``invited`` status so they must complete enrollment before
        # they get full access. The /auth/login endpoint enforces the
        # mfa_required contract for admin accounts automatically.
        status=("invited" if mfa_required else status_value),
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "first_name": new_user.first_name,
        "last_name": new_user.last_name,
        "role": getattr(new_user.role, "value", new_user.role),
        "status": str(getattr(new_user.status, "value", new_user.status)),
        "mfa_enabled": bool(new_user.mfa_enabled),
        "mfa_required": mfa_required,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
    }
