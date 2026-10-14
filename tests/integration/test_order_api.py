"""Integration tests for the order API."""

import pytest
from uuid import uuid4

from apps.api.modules.order.services import (
    list_orders,
    get_order,
    update_order_status,
)
from infalette_commerce.schemas import OrderStatusUpdate
from infalette_database.models.order import Order, OrderStatus


@pytest.mark.asyncio
async def test_list_orders_empty(db_session, tenant_id):
    """Test listing orders when none exist."""
    orders = await list_orders(tenant_id, db_session)
    assert orders == []


@pytest.mark.asyncio
async def test_create_and_get_order(db_session, tenant_id, customer_id):
    """Test creating and retrieving an order."""
    order = Order(
        tenant_id=tenant_id,
        customer_id=customer_id,
        checkout_id=None,
        status=OrderStatus.CONFIRMED,
        total_cents=10000,
        currency="INR",
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)

    retrieved = await get_order(tenant_id, order.id, db_session)
    assert retrieved is not None
    assert retrieved.total_cents == 10000
    assert retrieved.status == OrderStatus.CONFIRMED


@pytest.mark.asyncio
async def test_update_order_status(db_session, tenant_id, customer_id):
    """Test updating order status."""
    order = Order(
        tenant_id=tenant_id,
        customer_id=customer_id,
        status=OrderStatus.CONFIRMED,
        total_cents=10000,
        currency="INR",
    )
    db_session.add(order)
    await db_session.commit()

    data = OrderStatusUpdate(status=OrderStatus.PROCESSING)
    updated = await update_order_status(tenant_id, order.id, data, db_session)

    assert updated.status == OrderStatus.PROCESSING


@pytest.mark.asyncio
async def test_update_order_status_invalid_transition(db_session, tenant_id, customer_id):
    """Test that invalid status transitions are rejected."""
    order = Order(
        tenant_id=tenant_id,
        customer_id=customer_id,
        status=OrderStatus.CONFIRMED,
        total_cents=10000,
        currency="INR",
    )
    db_session.add(order)
    await db_session.commit()

    # Cannot go from CONFIRMED to DELIVERED directly
    data = OrderStatusUpdate(status=OrderStatus.DELIVERED)
    with pytest.raises(ValueError, match="Invalid status transition"):
        await update_order_status(tenant_id, order.id, data, db_session)


@pytest.mark.asyncio
async def test_get_order_not_found(db_session, tenant_id):
    """Test getting a non-existent order."""
    result = await get_order(tenant_id, uuid4(), db_session)
    assert result is None
