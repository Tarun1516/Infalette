"""Sitemap generation task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_config import get_settings
from infalette_database.models.store import Store
from infalette_seo.sitemap_generator import SitemapGenerator

logger = logging.getLogger(__name__)


async def generate_sitemaps(
    session: AsyncSession,
    tenant_id: UUID = None,
) -> dict:
    """Generate sitemaps for tenants."""
    query = select(Store)
    if tenant_id:
        query = query.where(Store.tenant_id == tenant_id)

    result = await session.execute(query)
    stores = list(result.scalars().all())

    generator = SitemapGenerator()
    generated = 0
    uploaded = 0
    errors = 0

    # Optional S3 persistence — when a bucket is configured, the XML is
    # uploaded so the CDN can serve /sitemaps/{tenant_id}.xml directly.
    s3_client = None
    try:
        from infalette_integrations.s3.client import S3Client

        settings_bucket = get_settings().email.s3_bucket
        if settings_bucket:
            s3_client = S3Client()
    except Exception:
        s3_client = None

    for store in stores:
        try:
            urls = await generator.generate_sitemap(store.tenant_id, session)
            xml = generator.generate_sitemap_xml(urls)
            logger.info(f"Generated sitemap for tenant {store.tenant_id}: {len(urls)} URLs")
            generated += 1

            if s3_client:
                try:
                    key = f"sitemaps/{store.tenant_id}.xml"
                    import asyncio as _asyncio

                    await _asyncio.to_thread(
                        s3_client.upload_file, xml.encode("utf-8"), key, "application/xml"
                    )
                    uploaded += 1
                except Exception as e:
                    logger.warning(
                        "S3 upload failed for tenant %s sitemap: %s", store.tenant_id, e
                    )
        except Exception as e:
            logger.error(f"Error generating sitemap for tenant {store.tenant_id}: {e}", exc_info=True)
            errors += 1

    return {
        "stores_processed": len(stores),
        "generated": generated,
        "uploaded_to_s3": uploaded,
        "errors": errors,
        "generated_at": datetime.utcnow().isoformat(),
    }


@shared_task(name="apps.workers.tasks.sitemap.generate_sitemaps")
def generate_sitemaps_task() -> dict:
    """Celery entry point: regenerate per-store sitemaps."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            return await generate_sitemaps(session)

    return asyncio.run(_run())
