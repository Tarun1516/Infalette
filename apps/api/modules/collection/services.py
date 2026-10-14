"""Collection management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.collection import Collection
from infalette_database.models.product import Product


async def list_collections(
    tenant_id: UUID,
    session: AsyncSession,
    status: Optional[str] = None,
) -> list[Collection]:
    """List collections for a tenant."""
    query = select(Collection).where(Collection.tenant_id == tenant_id)
    if status:
        query = query.where(Collection.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_collection(
    tenant_id: UUID,
    collection_id: UUID,
    session: AsyncSession,
) -> Collection | None:
    """Get a collection by ID."""
    result = await session.execute(
        select(Collection).where(
            Collection.id == collection_id,
            Collection.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_collection(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Collection:
    """Create a new collection."""
    collection = Collection(
        tenant_id=tenant_id,
        name=data.get("name"),
        slug=data.get("slug"),
        description=data.get("description", ""),
        sort_order=data.get("sort_order", 0),
        status=data.get("status", "active"),
        seo_title=data.get("seo_title"),
        seo_description=data.get("seo_description"),
        product_ids=data.get("product_ids", []),
        rules=data.get("rules", []),
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return collection


async def update_collection(
    tenant_id: UUID,
    collection_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Collection | None:
    """Update a collection."""
    collection = await get_collection(tenant_id, collection_id, session)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    for key, value in data.items():
        if hasattr(collection, key) and value is not None:
            setattr(collection, key, value)

    await session.commit()
    await session.refresh(collection)
    return collection


async def delete_collection(
    tenant_id: UUID,
    collection_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete a collection."""
    await session.execute(
        delete(Collection).where(
            Collection.id == collection_id,
            Collection.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def get_collection_products(
    tenant_id: UUID,
    collection_id: UUID,
    session: AsyncSession,
) -> list[Product]:
    """Get all products in a collection."""
    collection = await get_collection(tenant_id, collection_id, session)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    product_ids = collection.product_ids or []
    if not product_ids:
        return []

    result = await session.execute(
        select(Product).where(
            Product.id.in_(product_ids),
            Product.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())
