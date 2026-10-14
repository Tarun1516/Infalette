"""Page management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/", response_model=list[dict])
async def list_pages(
    store_id: Optional[UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List pages for the current tenant."""
    from apps.api.modules.page.services import list_pages as svc_list
    pages = await svc_list(user.tenant_id, session, store_id=store_id, status=status_filter)
    return [
        {
            "id": str(p.id),
            "tenant_id": str(p.tenant_id),
            "store_id": str(p.store_id) if p.store_id else None,
            "title": p.title,
            "slug": p.slug,
            "path": getattr(p, "path", f"/{p.slug}"),
            "blocks_json": getattr(p, "blocks_json", []) or [],
            "status": p.status.value if hasattr(p.status, "value") else p.status,
            "is_homepage": getattr(p, "is_homepage", False),
            "meta_title": getattr(p, "meta_title", None),
            "meta_description": getattr(p, "meta_description", None),
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in pages
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_page(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new page."""
    from apps.api.modules.page.services import create_page as svc_create
    page = await svc_create(user.tenant_id, data, session)
    return {
        "id": str(page.id),
        "tenant_id": str(page.tenant_id),
        "store_id": str(page.store_id) if page.store_id else None,
        "title": page.title,
        "slug": page.slug,
        "path": getattr(page, "path", f"/{page.slug}"),
        "blocks_json": getattr(page, "blocks_json", []) or [],
        "status": page.status.value if hasattr(page.status, "value") else page.status,
        "is_homepage": getattr(page, "is_homepage", False),
        "meta_title": getattr(page, "meta_title", None),
        "meta_description": getattr(page, "meta_description", None),
    }


@router.get("/{page_id}")
async def get_page(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a page by ID."""
    from apps.api.modules.page.services import get_page as svc_get
    page = await svc_get(user.tenant_id, page_id, session)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {
        "id": str(page.id),
        "tenant_id": str(page.tenant_id),
        "store_id": str(page.store_id) if page.store_id else None,
        "title": page.title,
        "slug": page.slug,
        "path": getattr(page, "path", f"/{page.slug}"),
        "blocks_json": getattr(page, "blocks_json", []) or [],
        "status": page.status.value if hasattr(page.status, "value") else page.status,
        "is_homepage": getattr(page, "is_homepage", False),
        "meta_title": getattr(page, "meta_title", None),
        "meta_description": getattr(page, "meta_description", None),
        "created_at": page.created_at.isoformat() if page.created_at else None,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }


@router.patch("/{page_id}")
async def update_page(
    page_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a page."""
    from apps.api.modules.page.services import update_page as svc_update
    page = await svc_update(user.tenant_id, page_id, data, session)
    return {
        "id": str(page.id),
        "tenant_id": str(page.tenant_id),
        "store_id": str(page.store_id) if page.store_id else None,
        "title": page.title,
        "slug": page.slug,
        "path": getattr(page, "path", f"/{page.slug}"),
        "blocks_json": getattr(page, "blocks_json", []) or [],
        "status": page.status.value if hasattr(page.status, "value") else page.status,
        "is_homepage": getattr(page, "is_homepage", False),
        "meta_title": getattr(page, "meta_title", None),
        "meta_description": getattr(page, "meta_description", None),
    }


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a page."""
    from apps.api.modules.page.services import delete_page as svc_delete
    await svc_delete(user.tenant_id, page_id, session)
    return None


@router.post("/{page_id}/publish")
async def publish_page(
    page_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Publish a page (set status to published)."""
    from apps.api.modules.page.services import publish_page as svc_publish
    page = await svc_publish(user.tenant_id, page_id, session)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {
        "id": str(page.id),
        "status": page.status.value if hasattr(page.status, "value") else page.status,
        "message": "Page published",
    }


# Proxy endpoint for GET /stores/{store_id}/pages when mounted via page router
# Note: When router is mounted at /api/v1/pages, this becomes /api/v1/pages/stores/{store_id}/pages
# The canonical GET /stores/{store_id}/pages is implemented in store/routes.py.
# This handler is kept for compatibility if someone calls the nested path.
@router.get("/stores/{store_id}/pages")
async def list_store_pages_via_page_router(
    store_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List pages for a specific store (via page router nested path)."""
    from apps.api.modules.page.services import list_store_pages
    pages = await list_store_pages(user.tenant_id, store_id, session)
    return [
        {
            "id": str(p.id),
            "tenant_id": str(p.tenant_id),
            "store_id": str(p.store_id) if p.store_id else None,
            "title": p.title,
            "slug": p.slug,
            "path": getattr(p, "path", f"/{p.slug}"),
            "blocks_json": getattr(p, "blocks_json", []) or [],
            "status": p.status.value if hasattr(p.status, "value") else p.status,
            "is_homepage": getattr(p, "is_homepage", False),
            "meta_title": getattr(p, "meta_title", None),
            "meta_description": getattr(p, "meta_description", None),
        }
        for p in pages
    ]
