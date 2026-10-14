"""Store management routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from infalette_validation.schemas import StoreCreate, StoreRead

router = APIRouter()


@router.get("/settings")
async def get_store_settings(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get store settings for current tenant (first store)."""
    from apps.api.modules.store.services import get_store_settings
    settings = await get_store_settings(user.tenant_id, session)
    if not settings:
        raise HTTPException(status_code=404, detail="Store settings not found")
    # Return raw dict for flexibility, but also compatible with StoreRead
    return settings


@router.patch("/settings")
async def update_store_settings(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update store settings for current tenant (first store)."""
    from apps.api.modules.store.services import update_store_settings
    updated = await update_store_settings(user.tenant_id, data, session)
    if not updated:
        raise HTTPException(status_code=404, detail="Store not found")
    return updated


@router.get("/{store_id}/pages")
async def get_store_pages(
    store_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get pages for a specific store (proxy to page service)."""
    from apps.api.modules.page.services import list_store_pages
    pages = await list_store_pages(user.tenant_id, store_id, session)
    # Return simplified list
    return [
        {
            "id": str(p.id),
            "tenant_id": str(p.tenant_id),
            "store_id": str(p.store_id) if p.store_id else None,
            "title": p.title,
            "slug": p.slug,
            "path": getattr(p, "path", f"/{p.slug}"),
            "blocks_json": getattr(p, "blocks_json", []) or [],
            "status": p.status.value if hasattr(p.status, "value") else p.status,
            "is_homepage": getattr(p, "is_homepage", False),
            "meta_title": getattr(p, "meta_title", None),
            "meta_description": getattr(p, "meta_description", None),
        }
        for p in pages
    ]


@router.post("/", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
async def create_store(
    data: StoreCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new store."""
    from apps.api.modules.store.services import create_store
    tenant_id = user.tenant_id
    return await create_store(tenant_id, data, session)


@router.get("/{store_id}", response_model=StoreRead)
async def get_store(
    store_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a store by ID – tenant isolated."""
    from apps.api.modules.store.services import get_store
    store = await get_store(store_id, session, tenant_id=user.tenant_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/", response_model=list[StoreRead])
async def list_stores(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List all stores for the current tenant."""
    from apps.api.modules.store.services import list_stores
    tenant_id = user.tenant_id
    return await list_stores(tenant_id, session)


@router.put("/{store_id}", response_model=StoreRead)
async def update_store(
    store_id: UUID,
    data: StoreCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a store – tenant isolated."""
    from apps.api.modules.store.services import update_store
    store = await update_store(store_id, data, session, tenant_id=user.tenant_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a store – tenant isolated."""
    from apps.api.modules.store.services import delete_store
    await delete_store(store_id, session, tenant_id=user.tenant_id)
