"""SEO management routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def list_seo_pages(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List SEO pages for the tenant."""
    from apps.api.modules.seo.services import list_seo_pages
    return await list_seo_pages(user.tenant_id, session)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_seo_page(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new SEO page."""
    from apps.api.modules.seo.services import create_seo_page
    return await create_seo_page(user.tenant_id, data, session)


# ----------------------------------------------------------------- redirects
@router.get("/redirects")
async def list_redirects(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List URL redirects for the tenant."""
    from sqlalchemy import select

    from infalette_database.models.seo_redirect import SeoRedirect

    result = await session.execute(
        select(SeoRedirect).where(SeoRedirect.tenant_id == user.tenant_id)
    )
    return [_redirect_dict(r) for r in result.scalars().all()]


@router.post("/redirects", status_code=status.HTTP_201_CREATED)
async def create_redirect(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a redirect (old_path -> new_path, 301|302)."""
    from infalette_database.models.seo_redirect import SeoRedirect

    old_path = str(data.get("old_path") or "").strip()
    new_path = str(data.get("new_path") or "").strip()
    if not old_path.startswith("/") or not new_path.startswith("/"):
        raise HTTPException(status_code=422, detail="old_path/new_path must start with '/'")
    status_code = int(data.get("status_code", 301))
    if status_code not in (301, 302, 308):
        raise HTTPException(status_code=422, detail="status_code must be 301, 302 or 308")

    existing = (
        await session.execute(
            select(SeoRedirect).where(
                SeoRedirect.tenant_id == user.tenant_id,
                SeoRedirect.old_path == old_path,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.new_path = new_path
        existing.status_code = status_code
        await session.commit()
        await session.refresh(existing)
        return _redirect_dict(existing)

    redirect = SeoRedirect(
        tenant_id=user.tenant_id,
        old_path=old_path,
        new_path=new_path,
        status_code=status_code,
    )
    session.add(redirect)
    await session.commit()
    await session.refresh(redirect)
    return _redirect_dict(redirect)


@router.delete("/redirects/{redirect_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_redirect(
    redirect_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a redirect."""
    from sqlalchemy import delete as sa_delete

    from infalette_database.models.seo_redirect import SeoRedirect

    result = await session.execute(
        sa_delete(SeoRedirect).where(
            SeoRedirect.id == redirect_id,
            SeoRedirect.tenant_id == user.tenant_id,
        )
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Redirect not found")


def _redirect_dict(r) -> dict:
    return {
        "id": str(r.id),
        "old_path": r.old_path,
        "new_path": r.new_path,
        "status_code": r.status_code,
        "is_active": r.is_active,
    }


@router.get("/{page_id}")
async def get_seo_page(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get an SEO page by ID."""
    from apps.api.modules.seo.services import get_seo_page
    page = await get_seo_page(user.tenant_id, page_id, session)
    if not page:
        raise HTTPException(status_code=404, detail="SEO page not found")
    return page


@router.patch("/{page_id}")
async def update_seo_page(
    page_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update an SEO page."""
    from apps.api.modules.seo.services import update_seo_page
    return await update_seo_page(user.tenant_id, page_id, data, session)


@router.delete("/{page_id}")
async def delete_seo_page(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete an SEO page."""
    from apps.api.modules.seo.services import delete_seo_page
    await delete_seo_page(user.tenant_id, page_id, session)
    return {"message": "SEO page deleted"}


@router.post("/sitemap/generate")
async def generate_sitemap(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Generate a sitemap for the tenant."""
    from apps.api.modules.seo.services import generate_sitemap
    return await generate_sitemap(user.tenant_id, session)


@router.post("/meta-tags/generate")
async def generate_meta_tags(
    page_data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Generate meta tags for a page."""
    from apps.api.modules.seo.services import generate_meta_tags
    return await generate_meta_tags(user.tenant_id, page_data, session)
