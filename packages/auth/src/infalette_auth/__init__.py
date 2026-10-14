"""Infalette authentication and authorization package."""

from infalette_auth.security import PasswordHasher
from infalette_auth.jwt import TokenManager
from infalette_auth.mfa import MFAService
from infalette_auth.rbac import RBACService
from infalette_auth.tenant import TenantResolver
from infalette_auth.clerk import verify_clerk_token, resolve_jwks_url
from infalette_auth.dependencies import (
    get_current_user,
    get_current_active_user,
    require_role,
    require_permission,
    get_tenant_context,
)

__all__ = [
    "PasswordHasher",
    "TokenManager",
    "MFAService",
    "RBACService",
    "TenantResolver",
    "verify_clerk_token",
    "resolve_jwks_url",
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "require_permission",
    "get_tenant_context",
]
