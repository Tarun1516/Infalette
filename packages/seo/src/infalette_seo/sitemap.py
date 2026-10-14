"""Sitemap and robots.txt generation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_config import get_settings
from infalette_database.models.product import Product
from infalette_database.models.page import Page


def _base_url() -> str:
    """Base storefront URL for sitemap entries (no trailing slash)."""
    settings = get_settings()
    url = getattr(settings, "storefront_url", None) or getattr(settings, "api_url", "http://localhost:3000")
    return str(url).rstrip("/")


async def generate_sitemap(tenant_id: UUID, session: AsyncSession) -> str:
    """Generate XML sitemap for a tenant."""
    base = _base_url()
    urls = []

    result = await session.execute(
        select(Product).where(Product.tenant_id == tenant_id)
    )
    for product in result.scalars().all():
        urls.append(f"  <url><loc>{base}/products/{product.slug}</loc></url>")

    result = await session.execute(
        select(Page).where(Page.tenant_id == tenant_id, Page.status == "published")
    )
    for page in result.scalars().all():
        page_path = page.path or page.slug
        urls.append(f"  <url><loc>{base}/{page_path}</loc></url>")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


async def generate_robots_txt(tenant_id: UUID, session: AsyncSession) -> str:
    """Generate robots.txt for a tenant."""
    return f"""User-agent: *
Allow: /
Sitemap: {_base_url()}/sitemap.xml
"""
