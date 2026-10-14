"""Category management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.category import Category
from infalette_database.models.product import Product


async def list_categories(
    tenant_id: UUID,
    session: AsyncSession,
    parent_id: Optional[UUID] = None,
) -> list[Category]:
    """List categories for a tenant."""
    query = select(Category).where(Category.tenant_id == tenant_id)
    if parent_id:
        query = query.where(Category.parent_id == parent_id)
    else:
        query = query.where(Category.parent_id.is_(None))
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_category(
    tenant_id: UUID,
    category_id: UUID,
    session: AsyncSession,
) -> Category | None:
    """Get a category by ID."""
    result = await session.execute(
        select(Category).where(
            Category.id == category_id,
            Category.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_category(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Category:
    """Create a new category."""
    category = Category(
        tenant_id=tenant_id,
        name=data.get("name"),
        slug=data.get("slug"),
        description=data.get("description", ""),
        parent_id=data.get("parent_id"),
        seo_title=data.get("seo_title"),
        seo_description=data.get("seo_description"),
        sort_order=data.get("sort_order", 0),
        status=data.get("status", "active"),
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update_category(
    tenant_id: UUID,
    category_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Category | None:
    """Update a category."""
    category = await get_category(tenant_id, category_id, session)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for key, value in data.items():
        if hasattr(category, key) and value is not None:
            setattr(category, key, value)

    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(
    tenant_id: UUID,
    category_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete a category."""
    await session.execute(
        delete(Category).where(
            Category.id == category_id,
            Category.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def get_category_products(
    tenant_id: UUID,
    category_id: UUID,
    session: AsyncSession,
) -> list[Product]:
    """Get all products in a category."""
    result = await session.execute(
        select(Product).where(
            Product.category_id == category_id,
            Product.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())


async def get_category_tree(
    tenant_id: UUID,
    session: AsyncSession,
) -> list[dict]:
    """Get the category tree."""
    result = await session.execute(
        select(Category).where(Category.tenant_id == tenant_id)
    )
    categories = list(result.scalars().all())

    # Build tree
    tree = []
    cat_map = {c.id: {"id": str(c.id), "name": c.name, "slug": c.slug, "children": []} for c in categories}

    for c in categories:
        if c.parent_id is None:
            tree.append(cat_map[c.id])
        else:
            if c.parent_id in cat_map:
                cat_map[c.parent_id]["children"].append(cat_map[c.id])

    return tree
