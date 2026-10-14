"""Collection management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def list_collections(
    status: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List collections for the tenant."""
    from apps.api.modules.collection.services import list_collections
    return await list_collections(user.tenant_id, session, status)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new collection."""
    from apps.api.modules.collection.services import create_collection
    return await create_collection(user.tenant_id, data, session)


@router.get("/{collection_id}")
async def get_collection(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a collection by ID."""
    from apps.api.modules.collection.services import get_collection
    collection = await get_collection(user.tenant_id, collection_id, session)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.patch("/{collection_id}")
async def update_collection(
    collection_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a collection."""
    from apps.api.modules.collection.services import update_collection
    return await update_collection(user.tenant_id, collection_id, data, session)


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a collection."""
    from apps.api.modules.collection.services import delete_collection
    await delete_collection(user.tenant_id, collection_id, session)
    return {"message": "Collection deleted"}


@router.get("/{collection_id}/products")
async def get_collection_products(
    collection_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get all products in a collection."""
    from apps.api.modules.collection.services import get_collection_products
    return await get_collection_products(user.tenant_id, collection_id, session)
