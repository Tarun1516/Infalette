"""Product management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from infalette_validation.schemas import ProductCreate, ProductRead
from apps.api.core.feature_flags import enforce_quota

router = APIRouter()


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
    quota=Depends(enforce_quota("products")),
):
    """Create a new product (plan quota enforced)."""
    from apps.api.modules.product.services import create_product
    return await create_product(user.tenant_id, data, session)


@router.post("/import")
async def import_products(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Bulk import/update products from a CSV file (onboarding imports).

    Upserts by SKU within the tenant; honours the plan product quota.
    Returns {"created": n, "updated": n, "skipped": n, "errors": [...]}.
    """
    from apps.api.modules.product.services import import_products_csv

    content = await file.read()
    try:
        return await import_products_csv(user.tenant_id, content, session)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a product by ID."""
    from apps.api.modules.product.services import get_product
    product = await get_product(user.tenant_id, product_id, session)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/")
async def list_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List products for the tenant (paginated + searchable)."""
    from apps.api.modules.product.services import list_products
    return await list_products(
        user.tenant_id,
        session,
        page=page,
        per_page=per_page,
        search=search,
        category_id=category_id,
    )


@router.put("/{product_id}", response_model=ProductRead)
@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    data: ProductCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Full update of a product. Both PUT and PATCH are accepted for
    backward compatibility with form-style editors."""
    from apps.api.modules.product.services import update_product
    product = await update_product(user.tenant_id, product_id, data, session)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}/stock", response_model=dict)
async def adjust_product_stock(
    product_id: UUID,
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Partial update for inventory adjustments.

    Body: ``{"inventory_quantity": <int>}`` (also accepts the legacy
    ``inventory`` field). The endpoint clamps the new value to ``>= 0``
    and writes back to both ``inventory_quantity`` (canonical) and the
    legacy ``inventory`` column for backwards compatibility with the
    storefront's ``inventory_quantity`` reader.
    """
    from apps.api.modules.product.services import adjust_stock

    next_qty = payload.get("inventory_quantity")
    if next_qty is None:
        next_qty = payload.get("inventory")
    if next_qty is None:
        raise HTTPException(status_code=422, detail="inventory_quantity is required")
    try:
        next_qty = int(next_qty)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="inventory_quantity must be an integer")
    next_qty = max(0, next_qty)

    updated = await adjust_stock(user.tenant_id, product_id, next_qty, session)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": str(updated.id),
        "inventory_quantity": int(updated.inventory_quantity or 0),
        "inventory": int(updated.inventory or 0),
    }


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a product."""
    from apps.api.modules.product.services import delete_product
    await delete_product(user.tenant_id, product_id, session)


@router.get("/{product_id}/variants", response_model=list[dict])
async def list_variants(
    product_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List all variants for a product."""
    from apps.api.modules.product.services import get_product, list_variants
    product = await get_product(user.tenant_id, product_id, session)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return await list_variants(user.tenant_id, product_id, session)


@router.post("/{product_id}/variants", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_variant(
    product_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new variant for a product."""
    from apps.api.modules.product.services import create_variant
    variant = await create_variant(user.tenant_id, product_id, data, session)
    if not variant:
        raise HTTPException(status_code=404, detail="Product not found")
    return variant


@router.get("/{product_id}/variants/{variant_id}", response_model=dict)
async def get_variant(
    product_id: UUID,
    variant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a variant by ID."""
    from apps.api.modules.product.services import get_variant
    variant = await get_variant(user.tenant_id, product_id, variant_id, session)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


@router.patch("/{product_id}/variants/{variant_id}", response_model=dict)
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a variant."""
    from apps.api.modules.product.services import update_variant
    variant = await update_variant(user.tenant_id, product_id, variant_id, data, session)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


@router.delete("/{product_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a variant."""
    from apps.api.modules.product.services import delete_variant
    deleted = await delete_variant(user.tenant_id, product_id, variant_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Variant not found")
