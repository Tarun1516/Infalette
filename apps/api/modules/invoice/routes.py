"""Invoice API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/{order_id}", response_model=dict)
async def get_invoice(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get invoice data for an order – tenant isolated.

    Returns JSON invoice with invoice_number, line items, totals, GST breakdown.
    """
    from apps.api.modules.invoice.services import get_invoice as svc_get_invoice
    return await svc_get_invoice(user.tenant_id, order_id, session)


@router.get("/{order_id}/download")
async def download_invoice(
    order_id: UUID,
    format: str = Query(default="html", description="html or pdf"),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Download invoice as HTML or PDF – tenant isolated.

    Query param `format` controls output: 'html' returns text/html, 'pdf' returns application/pdf.
    Falls back to HTML bytes if weasyprint not installed.
    """
    from apps.api.modules.invoice.services import get_invoice_html, get_invoice_pdf, get_invoice

    fmt = (format or "html").lower()
    if fmt == "pdf":
        pdf_bytes = await get_invoice_pdf(user.tenant_id, order_id, session)
        # Check if bytes start with PDF magic %PDF; else it's HTML fallback
        is_pdf = pdf_bytes.startswith(b"%PDF")
        if is_pdf:
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="invoice-{order_id}.pdf"'},
            )
        else:
            # Fallback HTML bytes but serve as PDF? Serve as HTML
            return HTMLResponse(content=pdf_bytes.decode("utf-8", errors="replace"))
    else:
        html = await get_invoice_html(user.tenant_id, order_id, session)
        # If client expects download, set disposition; otherwise inline
        return HTMLResponse(
            content=html,
            headers={"Content-Disposition": f'inline; filename="invoice-{order_id}.html"'},
        )


@router.get("/{order_id}/html", response_class=HTMLResponse)
async def get_invoice_html_route(
    order_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Render invoice as HTML page."""
    from apps.api.modules.invoice.services import get_invoice_html
    html = await get_invoice_html(user.tenant_id, order_id, session)
    return HTMLResponse(content=html)
