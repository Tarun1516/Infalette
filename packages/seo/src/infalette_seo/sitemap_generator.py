"""Sitemap generation for SEO."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.product import Product
from infalette_database.models.category import Category
from infalette_database.models.collection import Collection
from infalette_database.models.store import Store


def _base_url() -> str:
    """Storefront base URL from settings (no trailing slash)."""
    try:
        from infalette_config import get_settings

        return str(get_settings().storefront_url or "http://localhost:3000").rstrip("/")
    except Exception:
        return "http://localhost:3000"


class SitemapGenerator:
    """Generates sitemaps for a tenant's storefront."""

    async def generate_sitemap(
        self,
        tenant_id: UUID,
        session: AsyncSession,
        base_url: str | None = None,
    ) -> list[dict]:
        """Generate a sitemap for the tenant."""
        base = (base_url or _base_url()).rstrip("/")
        urls = []

        # Homepage
        urls.append({
            "loc": f"{base}/{tenant_id}",
            "changefreq": "daily",
            "priority": 1.0,
        })

        # Products
        result = await session.execute(
            select(Product).where(Product.tenant_id == tenant_id)
        )
        for product in result.scalars().all():
            urls.append({
                "loc": f"{base}/{tenant_id}/product/{product.slug}",
                "lastmod": product.updated_at.isoformat() if product.updated_at else None,
                "changefreq": "weekly",
                "priority": 0.8,
            })

        # Categories
        result = await session.execute(
            select(Category).where(Category.tenant_id == tenant_id)
        )
        for category in result.scalars().all():
            urls.append({
                "loc": f"{base}/{tenant_id}/category/{category.slug}",
                "changefreq": "weekly",
                "priority": 0.7,
            })

        # Collections
        result = await session.execute(
            select(Collection).where(Collection.tenant_id == tenant_id)
        )
        for collection in result.scalars().all():
            urls.append({
                "loc": f"{base}/{tenant_id}/collection/{collection.slug}",
                "changefreq": "weekly",
                "priority": 0.7,
            })

        return urls

    def generate_sitemap_xml(self, urls: list[dict]) -> str:
        """Generate sitemap XML from URL list."""
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        for url in urls:
            xml_parts.append("  <url>")
            xml_parts.append(f"    <loc>{url['loc']}</loc>")
            if url.get("lastmod"):
                xml_parts.append(f"    <lastmod>{url['lastmod']}</lastmod>")
            if url.get("changefreq"):
                xml_parts.append(f"    <changefreq>{url['changefreq']}</changefreq>")
            if url.get("priority"):
                xml_parts.append(f"    <priority>{url['priority']}</priority>")
            xml_parts.append("  </url>")

        xml_parts.append("</urlset>")
        return "\n".join(xml_parts)
