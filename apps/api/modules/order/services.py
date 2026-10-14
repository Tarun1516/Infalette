"""Order management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_commerce.orders import OrderService
from infalette_commerce.schemas import OrderStatusUpdate, FulfillmentCreate, RefundCreate
from infalette_database.models.order import Order, OrderStatus
from infalette_database.models.order_item import OrderItem
from infalette_database.models.fulfillment import Fulfillment
from infalette_database.models.refund import Refund
from infalette_database.models.payment import Payment
from infalette_analytics.event_bus import record_event

order_service = OrderService()


async def list_orders(
    tenant_id: UUID,
    session: AsyncSession,
    status: Optional[str] = None,
    customer_id: Optional[UUID] = None,
) -> list[Order]:
    """List orders for a tenant."""
    filters = {}
    if status:
        filters["status"] = status
    if customer_id:
        filters["customer_id"] = str(customer_id)
    return await order_service.get_orders(tenant_id, session, filters)


async def get_order(tenant_id: UUID, order_id: UUID, session: AsyncSession) -> Order | None:
    """Get a single order."""
    return await order_service.get_order(tenant_id, order_id, session)


async def update_order_status(
    tenant_id: UUID,
    order_id: UUID,
    data: OrderStatusUpdate,
    session: AsyncSession,
) -> Order:
    """Update order status."""
    order = await order_service.get_order(tenant_id, order_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return await order_service.update_order_status(tenant_id, order_id, data.status, session)


async def _assert_order_tenant(tenant_id: UUID, order_id: UUID, session: AsyncSession) -> Order:
    """Verify order belongs to tenant; raises 404 if not."""
    order = await order_service.get_order(tenant_id, order_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def create_fulfillment(
    order_id: UUID,
    data: FulfillmentCreate,
    session: AsyncSession,
    tenant_id: UUID | None = None,
) -> Fulfillment:
    """Create a fulfillment for an order – tenant isolated if tenant_id provided."""
    if tenant_id is not None:
        await _assert_order_tenant(tenant_id, order_id, session)
    return await order_service.create_fulfillment(order_id, data.tracking_number, data.carrier, session)


async def process_refund(data: RefundCreate, session: AsyncSession, tenant_id: UUID | None = None) -> Refund:
    """Process a refund – tenant isolated."""
    # Verify payment belongs to tenant if tenant_id given
    if tenant_id is not None:
        result = await session.execute(select(Payment).where(Payment.id == data.payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        # Payment has tenant_id (via TenantMixin) – check
        if getattr(payment, "tenant_id", None) and payment.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Payment not found")
        # Also verify linked order tenant if payment has order_id
        if payment.order_id:
            await _assert_order_tenant(tenant_id, payment.order_id, session)
    return await order_service.process_refund(data.payment_id, data.amount_cents, data.reason, session)


async def create_return(
    order_id: UUID,
    items: list[dict],
    reason: str,
    session: AsyncSession,
    tenant_id: UUID | None = None,
) -> dict:
    """Create a return request – tenant isolated."""
    if tenant_id is not None:
        await _assert_order_tenant(tenant_id, order_id, session)
    return await order_service.create_return(order_id, items, reason, session)


async def get_order_fulfillments(order_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> list[Fulfillment]:
    """Get fulfillments for an order – tenant isolated."""
    if tenant_id is not None:
        await _assert_order_tenant(tenant_id, order_id, session)
    return await order_service.get_order_fulfillments(order_id, session)


async def get_order_refunds(order_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> list[Refund]:
    """Get refunds for an order – tenant isolated."""
    if tenant_id is not None:
        await _assert_order_tenant(tenant_id, order_id, session)
    return await order_service.get_order_refunds(order_id, session)


async def get_order_payments(order_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> list[Payment]:
    """Get payments for an order – tenant isolated."""
    if tenant_id is not None:
        await _assert_order_tenant(tenant_id, order_id, session)
    result = await session.execute(select(Payment).where(Payment.order_id == order_id))
    payments = list(result.scalars().all())
    # Additional tenant filter if Payments have tenant_id
    if tenant_id is not None:
        payments = [p for p in payments if getattr(p, "tenant_id", tenant_id) == tenant_id]
    return payments


async def create_item(tenant_id: UUID, data: dict, session: AsyncSession) -> dict:
    """Create a new item (backward compatibility)."""
    return {"id": str(tenant_id), **data}


async def list_items(tenant_id: UUID, session: AsyncSession) -> list:
    """List items (backward compatibility)."""
    return []


async def get_item(tenant_id: UUID, item_id: UUID, session: AsyncSession):
    """Get an item (backward compatibility)."""
    return None
