"""Category management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def list_categories(
    parent_id: Optional[UUID] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List categories for the tenant."""
    from apps.api.modules.category.services import list_categories
    return await list_categories(user.tenant_id, session, parent_id)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_category(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new category."""
    from apps.api.modules.category.services import create_category
    return await create_category(user.tenant_id, data, session)


@router.get("/{category_id}")
async def get_category(
    category_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a category by ID."""
    from apps.api.modules.category.services import get_category
    category = await get_category(user.tenant_id, category_id, session)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.patch("/{category_id}")
async def update_category(
    category_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a category."""
    from apps.api.modules.category.services import update_category
    return await update_category(user.tenant_id, category_id, data, session)


@router.delete("/{category_id}")
async def delete_category(
    category_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a category."""
    from apps.api.modules.category.services import delete_category
    await delete_category(user.tenant_id, category_id, session)
    return {"message": "Category deleted"}


@router.get("/{category_id}/products")
async def get_category_products(
    category_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get all products in a category."""
    from apps.api.modules.category.services import get_category_products
    return await get_category_products(user.tenant_id, category_id, session)


@router.get("/tree")
@router.get("/tree/all")
async def get_category_tree(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get the category tree (``/tree`` and legacy ``/tree/all``)."""
    from apps.api.modules.category.services import get_category_tree
    return await get_category_tree(user.tenant_id, session)
