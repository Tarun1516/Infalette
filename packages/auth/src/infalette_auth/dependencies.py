"""FastAPI dependency functions for auth and tenant context."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from infalette_auth.jwt import TokenManager, TokenPayload
from infalette_auth.tenant import TenantResolver, TenantContext
from infalette_database.models.user import User
from infalette_database.models.role import UserRole
from infalette_database.session import get_async_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# Token manager singleton
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """Get or create the token manager singleton."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


async def get_current_user(
    request: Request,
    token_manager: TokenManager = Depends(get_token_manager),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Get the current authenticated user from the JWT token.

    Args:
        request: The FastAPI request.
        token_manager: The token manager.
        session: The database session.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: If the user is not authenticated.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]

    # 1. Try Clerk session JWT first (RS256 via JWKS) when Clerk is
    #    configured. Clerk user ids look like ``user_...`` and will never
    #    parse as UUID, so a Clerk token can never collide with legacy HS256.
    try:
        from infalette_auth.clerk import resolve_jwks_url, verify_clerk_token

        if resolve_jwks_url():
            claims = None
            try:
                claims = verify_clerk_token(token)
            except RuntimeError:
                claims = None  # not configured — fall through to legacy
            except Exception:
                claims = None  # not a Clerk token — try legacy below
            if claims is not None:
                clerk_user_id = claims.get("sub")
                # Prefer the linked local user; fall back to email match for
                # accounts created before the Clerk link existed.
                user = None
                if clerk_user_id and hasattr(User, "clerk_user_id"):
                    result = await session.execute(
                        select(User).where(User.clerk_user_id == clerk_user_id)
                    )
                    user = result.scalar_one_or_none()
                if user is None:
                    email = claims.get("email")
                    if email and isinstance(email, str):
                        result = await session.execute(
                            select(User).where(User.email == email.lower().strip())
                        )
                        user = result.scalar_one_or_none()
                        # Opportunistically link so next login hits the fast path.
                        if user is not None and hasattr(user, "clerk_user_id"):
                            try:
                                user.clerk_user_id = clerk_user_id
                                await session.commit()
                            except Exception:
                                await session.rollback()
                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Clerk user has no linked local account yet — sign up or wait for webhook sync",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return user
    except HTTPException:
        raise
    except Exception:
        # Never break legacy auth because Clerk helpers failed unexpectedly.
        pass

    try:
        payload = token_manager.decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    result = await session.execute(
        select(User).where(User.id == UUID(payload.sub))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Scope enforcement: MFA-enrollment tokens (issued to admins who have
    # not yet enrolled, spec §5 "MFA for admins") are valid only for the
    # MFA endpoints until enrollment completes.
    if getattr(payload, "scope", None) == "mfa_enrollment":
        path = request.url.path
        if not path.rstrip("/").endswith(("mfa/setup", "mfa/confirm-enrollment", "me")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA enrollment required before accessing this resource",
            )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user.

    Args:
        current_user: The current user from get_current_user.

    Returns:
        The active user.

    Raises:
        HTTPException: If the user is not active.
    """
    if current_user.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )
    return current_user


async def get_optional_user(
    request: Request,
    token_manager: TokenManager = Depends(get_token_manager),
    session: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """Return the authenticated user if a valid Bearer token is present, else None.

    Used by storefront guest flows (cart/checkout) where auth is optional.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    # Clerk first (optional flows must not break when Clerk is unconfigured).
    try:
        from infalette_auth.clerk import resolve_jwks_url, verify_clerk_token

        if resolve_jwks_url():
            try:
                claims = verify_clerk_token(token)
            except Exception:
                claims = None
            if claims is not None:
                clerk_user_id = claims.get("sub")
                try:
                    if clerk_user_id and hasattr(User, "clerk_user_id"):
                        result = await session.execute(
                            select(User).where(User.clerk_user_id == clerk_user_id)
                        )
                        user = result.scalar_one_or_none()
                        if user is not None:
                            return user
                except Exception:
                    pass
    except Exception:
        pass
    try:
        payload = token_manager.decode_token(token)
    except Exception:
        return None
    try:
        result = await session.execute(
            select(User).where(User.id == UUID(payload.sub))
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


def require_role(required_role: "UserRole | str"):
    """FastAPI dependency for role checking.

    Accepts a UserRole enum or plain string (users.role column values).
    Hierarchy-aware via RBACService.
    """
    from infalette_auth.rbac import RBACService

    _svc = RBACService()

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned",
            )
        if not _svc.check_role(current_user, required_role):
            req_value = getattr(required_role, "value", str(required_role))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {req_value}",
            )
        return current_user

    return role_checker


def require_permission(permission: str):
    """FastAPI dependency for permission checking."""
    from infalette_auth.rbac import RBACService

    _svc = RBACService()

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned",
            )
        if not _svc.check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}",
            )
        return current_user

    return permission_checker


def get_tenant_context(request: Request) -> TenantContext:
    """Get the tenant context from the request state.

    Args:
        request: The FastAPI request.

    Returns:
        The tenant context.
    """
    return request.state.tenant_context
