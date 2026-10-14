"""Discount/coupon management routes — tenant isolation + feature-flag aware."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import Feature, require_feature

router = APIRouter()

@router.get("/")
async def list_discounts(
    active_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.discount.services import list_discounts
    return await list_discounts(user.tenant_id, session, active_only=active_only)

@router.get("/{discount_id}")
async def get_discount(
    discount_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.discount.services import get_discount
    dc = await get_discount(user.tenant_id, discount_id, session)
    if not dc:
        raise HTTPException(status_code=404, detail="Discount not found")
    return dc

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_discount(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.discount.services import create_discount
    try:
        return await create_discount(user.tenant_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{discount_id}")
async def update_discount(
    discount_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.discount.services import update_discount
    dc = await update_discount(user.tenant_id, discount_id, data, session)
    if not dc:
        raise HTTPException(status_code=404, detail="Discount not found")
    return dc

@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount(
    discount_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.discount.services import delete_discount
    await delete_discount(user.tenant_id, discount_id, session)
    return None

@router.post("/{code}/validate")
async def validate_discount(
    code: str,
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Validate a coupon for a given order total — used by checkout preview."""
    from infalette_commerce.discounts import DiscountService
    total = int(payload.get("order_total_cents", 0))
    svc = DiscountService()
    try:
        res = await svc.validate_coupon_code(code.upper(), user.tenant_id, total, session)
        return {"valid": True, **res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
