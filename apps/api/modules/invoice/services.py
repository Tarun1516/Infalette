"""Invoice services for API."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from infalette_commerce.invoice import InvoiceService

invoice_service = InvoiceService()


async def get_invoice(tenant_id: UUID, order_id: UUID, session: AsyncSession) -> dict:
    """Get invoice data for an order, tenant-isolated."""
    from infalette_commerce.orders import OrderService
    order_service = OrderService()
    order = await order_service.get_order(tenant_id, order_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        data = await invoice_service.generate_invoice(order_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return data


async def get_invoice_html(tenant_id: UUID, order_id: UUID, session: AsyncSession) -> str:
    """Get invoice HTML."""
    from infalette_commerce.orders import OrderService
    order_service = OrderService()
    order = await order_service.get_order(tenant_id, order_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        html = await invoice_service.get_invoice_html(order_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return html


async def get_invoice_pdf(tenant_id: UUID, order_id: UUID, session: AsyncSession) -> bytes:
    """Get invoice PDF bytes."""
    from infalette_commerce.orders import OrderService
    order_service = OrderService()
    order = await order_service.get_order(tenant_id, order_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        pdf = await invoice_service.get_invoice_pdf(order_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return pdf
