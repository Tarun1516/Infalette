"""Order management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from infalette_commerce.schemas import OrderStatusUpdate, FulfillmentCreate, RefundCreate

router = APIRouter()


@router.get("/", response_model=list)
async def list_orders(
    status: Optional[str] = Query(default=None),
    customer_id: Optional[UUID] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List orders for the tenant.

    Customer-role tokens are scoped to their own orders (they may only
    ever see what they bought); staff tokens see the whole tenant.
    """
    from apps.api.modules.order.services import list_orders

    effective_customer_id = customer_id
    if str(getattr(user, "role", "") or "").lower() == "customer":
        from infalette_database.models.customer import Customer

        own = (
            await session.execute(
                select(Customer).where(
                    Customer.tenant_id == user.tenant_id,
                    Customer.email == user.email,
                )
            )
        ).scalar_one_or_none()
        if own is None:
            return []
        # Customers can never widen their scope via the query param.
        effective_customer_id = own.id

    return await list_orders(user.tenant_id, session, status, effective_customer_id)


@router.get("/{order_id}")
async def get_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get an order by ID."""
    from apps.api.modules.order.services import get_order
    order = await get_order(user.tenant_id, order_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update order status."""
    from apps.api.modules.order.services import update_order_status
    return await update_order_status(user.tenant_id, order_id, data, session)


@router.post("/{order_id}/fulfillments", status_code=status.HTTP_201_CREATED)
async def create_fulfillment(
    order_id: UUID,
    data: FulfillmentCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a fulfillment for an order – tenant isolated."""
    from apps.api.modules.order.services import create_fulfillment
    return await create_fulfillment(order_id, data, session, tenant_id=user.tenant_id)


@router.get("/{order_id}/fulfillments")
async def get_order_fulfillments(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get fulfillments for an order – tenant isolated."""
    from apps.api.modules.order.services import get_order_fulfillments
    return await get_order_fulfillments(order_id, session, tenant_id=user.tenant_id)


@router.post("/{order_id}/returns")
async def create_return(
    order_id: UUID,
    items: list[dict],
    reason: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a return request for an order – tenant isolated."""
    from apps.api.modules.order.services import create_return
    return await create_return(order_id, items, reason, session, tenant_id=user.tenant_id)


@router.post("/refunds", status_code=status.HTTP_201_CREATED)
async def process_refund(
    data: RefundCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Process a refund – tenant isolated."""
    from apps.api.modules.order.services import process_refund
    return await process_refund(data, session, tenant_id=user.tenant_id)


class OrderRefundRequest(BaseModel):
    """Refund an order by id; the payment is resolved server-side."""

    amount_cents: Optional[int] = None
    reason: Optional[str] = None


@router.post("/{order_id}/refunds", status_code=status.HTTP_201_CREATED)
async def refund_order(
    order_id: UUID,
    data: OrderRefundRequest,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Refund an order — resolves its succeeded payment automatically."""
    from sqlalchemy import select as _select

    from infalette_database.models.payment import Payment, PaymentStatus
    from infalette_database.models.order import Order
    from fastapi import HTTPException as _HTTPException

    order = (
        await session.execute(
            _select(Order).where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if not order:
        raise _HTTPException(status_code=404, detail="Order not found")

    payment = (
        await session.execute(
            _select(Payment).where(
                Payment.order_id == order_id,
                Payment.status == PaymentStatus.SUCCEEDED,
            )
        )
    ).scalars().first()
    if not payment:
        raise _HTTPException(
            status_code=422,
            detail="No succeeded payment found for this order (COD orders are refunded offline)",
        )

    from fastapi import HTTPException as _HTTPException

    _RefundCreate = RefundCreate  # already imported at module top (infalette_commerce.schemas)

    refund_data = _RefundCreate(
        payment_id=payment.id,
        amount_cents=data.amount_cents if data.amount_cents is not None else payment.amount_cents,
        reason=data.reason,
    )
    from apps.api.modules.order.services import process_refund
    return await process_refund(refund_data, session, tenant_id=user.tenant_id)


@router.get("/{order_id}/refunds")
async def get_order_refunds(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get refunds for an order – tenant isolated."""
    from apps.api.modules.order.services import get_order_refunds
    return await get_order_refunds(order_id, session, tenant_id=user.tenant_id)


@router.get("/{order_id}/payments")
async def get_order_payments(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get payments for an order – tenant isolated."""
    from apps.api.modules.order.services import get_order_payments
    return await get_order_payments(order_id, session, tenant_id=user.tenant_id)
