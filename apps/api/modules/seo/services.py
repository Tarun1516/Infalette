"""SEO management services."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.seo_page import SeoPage
from infalette_seo.sitemap_generator import SitemapGenerator
from infalette_seo.meta_tags import MetaTagGenerator


async def list_seo_pages(
    tenant_id: UUID,
    session: AsyncSession,
) -> list[SeoPage]:
    """List SEO pages for a tenant."""
    result = await session.execute(
        select(SeoPage).where(SeoPage.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def get_seo_page(
    tenant_id: UUID,
    page_id: UUID,
    session: AsyncSession,
) -> SeoPage | None:
    """Get an SEO page by ID."""
    result = await session.execute(
        select(SeoPage).where(
            SeoPage.id == page_id,
            SeoPage.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_seo_page(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> SeoPage:
    """Create a new SEO page."""
    page = SeoPage(
        tenant_id=tenant_id,
        url_path=data.get("url_path"),
        title=data.get("title"),
        meta_description=data.get("meta_description"),
        meta_keywords=data.get("meta_keywords"),
        canonical_url=data.get("canonical_url"),
        robots_index=data.get("robots_index", True),
        robots_follow=data.get("robots_follow", True),
        structured_data=data.get("structured_data", {}),
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return page


async def update_seo_page(
    tenant_id: UUID,
    page_id: UUID,
    data: dict,
    session: AsyncSession,
) -> SeoPage | None:
    """Update an SEO page."""
    page = await get_seo_page(tenant_id, page_id, session)
    if not page:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="SEO page not found")

    for key, value in data.items():
        if hasattr(page, key) and value is not None:
            setattr(page, key, value)

    await session.commit()
    await session.refresh(page)
    return page


async def delete_seo_page(
    tenant_id: UUID,
    page_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete an SEO page."""
    await session.execute(
        delete(SeoPage).where(
            SeoPage.id == page_id,
            SeoPage.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def generate_sitemap(
    tenant_id: UUID,
    session: AsyncSession,
) -> dict:
    """Generate a sitemap for the tenant."""
    generator = SitemapGenerator()
    urls = await generator.generate_sitemap(tenant_id, session)
    return {"urls": len(urls), "generated_at": datetime.utcnow().isoformat()}


async def generate_meta_tags(
    tenant_id: UUID,
    page_data: dict,
    session: AsyncSession,
) -> dict:
    """Generate meta tags for a page."""
    generator = MetaTagGenerator()
    return generator.generate_meta_tags(page_data)
