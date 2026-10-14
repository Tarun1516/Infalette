"""Checkout management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_optional_user
from apps.api.core.tenant_utils import resolve_tenant_id, get_cart_session_key
from infalette_validation.schemas import CheckoutCreate

router = APIRouter()


class PayRequest(BaseModel):
    """Request body for initiating payment."""

    provider: str = "razorpay"
    payment_provider: Optional[str] = None

    def resolved_provider(self) -> str:
        return (self.payment_provider or self.provider or "razorpay").lower().strip()


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_checkout(
    data: CheckoutCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_optional_user),
):
    """Create a checkout from the cart (guest checkout supported)."""
    from apps.api.modules.checkout.services import create_checkout

    tenant_id = await resolve_tenant_id(request, user, session)
    try:
        checkout = await create_checkout(
            tenant_id,
            user.id if user else None,
            data,
            session,
            session_key=get_cart_session_key(request) if user is None else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": str(checkout.id), "status": checkout.status.value, "total_cents": checkout.total_cents}


@router.get("/{checkout_id}", response_model=dict)
async def get_checkout(
    checkout_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_optional_user),
):
    """Get a checkout by ID."""
    from apps.api.modules.checkout.services import get_checkout

    tenant_id = await resolve_tenant_id(request, user, session)
    checkout = await get_checkout(tenant_id, checkout_id, session)
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout not found")
    return {"id": str(checkout.id), "status": checkout.status.value, "total_cents": checkout.total_cents}


@router.post("/{checkout_id}/pay", response_model=dict)
async def initiate_checkout_payment(
    checkout_id: UUID,
    request: Request,
    data: Optional[PayRequest] = Body(default=None),
    provider: Optional[str] = Query(default=None, description="Payment provider: razorpay, stripe, cod"),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_optional_user),
):
    """Initiate payment for a checkout.

    Supports razorpay, stripe, and cod (cash on delivery).
    For COD, order is created directly without external payment provider.
    Query param `provider` or body `{provider: str}` determines provider.
    """
    from apps.api.modules.checkout.services import initiate_payment

    tenant_id = await resolve_tenant_id(request, user, session)

    # Resolve provider from query > body > default
    resolved = None
    if provider:
        resolved = provider
    elif data is not None:
        resolved = data.resolved_provider()
    else:
        resolved = "razorpay"

    resolved = resolved.lower().strip()
    if resolved not in ("razorpay", "stripe", "cod"):
        raise HTTPException(status_code=400, detail=f"Unsupported payment provider: {resolved}. Use razorpay, stripe, or cod.")

    try:
        result = await initiate_payment(tenant_id, checkout_id, resolved, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/{checkout_id}/cod", response_model=dict)
async def create_cod_order(
    checkout_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_optional_user),
):
    """Shortcut for COD: create order directly for checkout via COD.

    Equivalent to POST /{checkout_id}/pay with provider=cod.
    """
    from apps.api.modules.checkout.services import initiate_payment

    tenant_id = await resolve_tenant_id(request, user, session)
    try:
        result = await initiate_payment(tenant_id, checkout_id, "cod", session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
