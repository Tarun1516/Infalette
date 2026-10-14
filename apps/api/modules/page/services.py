"""Page management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.page import Page, PageStatus


async def list_pages(
    tenant_id: UUID,
    session: AsyncSession,
    store_id: Optional[UUID] = None,
    status: Optional[str] = None,
) -> list[Page]:
    """List pages for a tenant, optionally filtered by store_id and status."""
    query = select(Page).where(Page.tenant_id == tenant_id)
    if store_id:
        query = query.where(Page.store_id == store_id)
    if status:
        query = query.where(Page.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_store_pages(
    tenant_id: UUID,
    store_id: UUID,
    session: AsyncSession,
) -> list[Page]:
    """List pages for a specific store (proxy helper for store routes)."""
    return await list_pages(tenant_id, session, store_id=store_id)


async def get_page(
    tenant_id: UUID,
    page_id: UUID,
    session: AsyncSession,
) -> Page | None:
    """Get a page by ID (tenant-scoped)."""
    result = await session.execute(
        select(Page).where(Page.id == page_id, Page.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_page(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Page:
    """Create a new page."""
    title = data.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    slug = data.get("slug")
    if not slug:
        slug = title.lower().replace(" ", "-").replace("_", "-")
    # Validate blocks if provided
    blocks = data.get("blocks_json") or data.get("blocks") or []
    if blocks:
        try:
            from infalette_validation.page_builder import validate_page_blocks
            validate_page_blocks(blocks)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid blocks: {e}")

    # Handle is_homepage uniqueness per store: if new page is_homepage, unset others
    is_homepage = data.get("is_homepage", False)
    store_id = data.get("store_id")

    if is_homepage and store_id:
        await session.execute(
            update(Page)
            .where(Page.tenant_id == tenant_id, Page.store_id == store_id, Page.is_homepage == True)  # noqa: E712
            .values(is_homepage=False)
            .execution_options(synchronize_session="fetch")
        )

    page = Page(
        tenant_id=tenant_id,
        store_id=store_id,
        title=title,
        slug=slug,
        path=data.get("path") or f"/{slug}",
        blocks_json=blocks,
        status=data.get("status", PageStatus.DRAFT),
        is_homepage=is_homepage,
        meta_title=data.get("meta_title"),
        meta_description=data.get("meta_description"),
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return page


async def update_page(
    tenant_id: UUID,
    page_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Page | None:
    """Update a page (PATCH)."""
    page = await get_page(tenant_id, page_id, session)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Validate blocks if provided
    if "blocks_json" in data or "blocks" in data:
        blocks = data.get("blocks_json") if "blocks_json" in data else data.get("blocks")
        if blocks is not None:
            try:
                from infalette_validation.page_builder import validate_page_blocks
                validate_page_blocks(blocks)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid blocks: {e}")
            page.blocks_json = blocks

    # Handle is_homepage toggle
    if "is_homepage" in data and data["is_homepage"] and page.store_id:
        await session.execute(
            update(Page)
            .where(
                Page.tenant_id == tenant_id,
                Page.store_id == page.store_id,
                Page.id != page_id,
                Page.is_homepage == True,  # noqa: E712
            )
            .values(is_homepage=False)
            .execution_options(synchronize_session="fetch")
        )

    for key in ["title", "slug", "path", "status", "is_homepage", "meta_title", "meta_description", "store_id"]:
        if key in data and data[key] is not None:
            setattr(page, key, data[key])

    # Auto-update path if slug changed and path not explicitly set
    if "slug" in data and "path" not in data:
        page.path = f"/{page.slug}"

    await session.commit()
    await session.refresh(page)
    return page


async def delete_page(
    tenant_id: UUID,
    page_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete a page."""
    await session.execute(
        delete(Page).where(Page.id == page_id, Page.tenant_id == tenant_id)
    )
    await session.commit()


async def publish_page(
    tenant_id: UUID,
    page_id: UUID,
    session: AsyncSession,
) -> Page | None:
    """Publish a page (set status to published)."""
    page = await get_page(tenant_id, page_id, session)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    await session.execute(
        update(Page)
        .where(Page.id == page_id, Page.tenant_id == tenant_id)
        .values(status=PageStatus.PUBLISHED)
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_page(tenant_id, page_id, session)
