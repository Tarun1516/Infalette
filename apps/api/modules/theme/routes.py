"""Theme management routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/presets")
async def get_presets(
    user=Depends(get_current_user),
):
    """Get 3 theme presets from packages/themes."""
    from apps.api.modules.theme.services import get_presets as svc_presets
    presets = await svc_presets()
    return presets


@router.post("/apply")
async def apply_theme(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Apply a theme preset or custom theme to a store."""
    from apps.api.modules.theme.services import apply_theme as svc_apply
    return await svc_apply(user.tenant_id, data, session)


@router.get("/", response_model=list[dict])
async def list_themes(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List themes for the current tenant."""
    from apps.api.modules.theme.services import list_themes as svc_list
    themes = await svc_list(user.tenant_id, session)
    return [
        {
            "id": str(t.id),
            "tenant_id": str(t.tenant_id),
            "name": t.name,
            "slug": t.slug,
            "config_json": getattr(t, "config_json", {}) or {},
            "is_default": getattr(t, "is_default", False),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in themes
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_theme(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new theme."""
    from apps.api.modules.theme.services import create_theme as svc_create
    theme = await svc_create(user.tenant_id, data, session)
    return {
        "id": str(theme.id),
        "tenant_id": str(theme.tenant_id),
        "name": theme.name,
        "slug": theme.slug,
        "config_json": getattr(theme, "config_json", {}) or {},
        "is_default": getattr(theme, "is_default", False),
    }


@router.get("/{theme_id}")
async def get_theme(
    theme_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a theme by ID."""
    from apps.api.modules.theme.services import get_theme as svc_get
    theme = await svc_get(user.tenant_id, theme_id, session)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return {
        "id": str(theme.id),
        "tenant_id": str(theme.tenant_id),
        "name": theme.name,
        "slug": theme.slug,
        "config_json": getattr(theme, "config_json", {}) or {},
        "is_default": getattr(theme, "is_default", False),
        "created_at": theme.created_at.isoformat() if theme.created_at else None,
        "updated_at": theme.updated_at.isoformat() if theme.updated_at else None,
    }


@router.patch("/{theme_id}")
async def update_theme(
    theme_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a theme."""
    from apps.api.modules.theme.services import update_theme as svc_update
    theme = await svc_update(user.tenant_id, theme_id, data, session)
    return {
        "id": str(theme.id),
        "tenant_id": str(theme.tenant_id),
        "name": theme.name,
        "slug": theme.slug,
        "config_json": getattr(theme, "config_json", {}) or {},
        "is_default": getattr(theme, "is_default", False),
    }


@router.delete("/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_theme(
    theme_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a theme."""
    from apps.api.modules.theme.services import delete_theme as svc_delete
    await svc_delete(user.tenant_id, theme_id, session)
    return None
