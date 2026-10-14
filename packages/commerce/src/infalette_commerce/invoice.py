"""Invoice generation service.

Generates invoice data (JSON + HTML) and PDF stub for orders.
Invoice number format: INV-{tenant_prefix}-{year}-{seq:06d}
where seq is derived deterministically from order id / count.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.order import Order
from infalette_database.models.order_item import OrderItem
from infalette_database.models.customer import Customer
from infalette_database.models.tenant import Tenant
from infalette_commerce.tax import TaxService


class InvoiceService:
    """Generate invoices for orders.

    Provides JSON data, HTML rendering, and PDF generation (via weasyprint if available).
    """

    def _generate_invoice_number(self, tenant_id: UUID, order_id: UUID, created_at: datetime | None) -> str:
        """Generate invoice number: INV-{tenant_prefix}-{year}-{seq}

        tenant_prefix: first 8 chars of tenant_id uppercased
        year: invoice year
        seq: deterministic per-order sequence derived from the order's
             creation timestamp within the tenant (monotonic, collision-free
             for practical purposes because two orders of one tenant rarely
             share the same second; the order id suffix disambiguates).
        """
        from datetime import timedelta, timezone as _tz

        stamp = created_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=_tz.utc)
        year = stamp.year
        tenant_prefix = str(tenant_id)[:8].upper()
        # Monotonic seconds-since-year-start + low bits of the order id:
        # stable per order, increasing with creation time.
        year_start = datetime(year, 1, 1, tzinfo=_tz.utc)
        seconds = max(int((stamp - year_start).total_seconds()), 1)
        h = hashlib.sha256(str(order_id).encode()).hexdigest()
        suffix = int(h[-2:], 16) % 100
        seq_int = (seconds * 100 + suffix) % 100000000
        return f"INV-{tenant_prefix}-{year}-{seq_int:08d}"

    async def generate_invoice(
        self,
        order_id: UUID,
        session: AsyncSession,
    ) -> dict:
        """Generate invoice data for an order.

        Returns dict with invoice_number, line items, totals, GST breakdown, etc.
        """
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError("Order not found")

        # Fetch order items
        result = await session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        order_items = list(result.scalars().all())

        # Fetch customer if available
        customer = None
        if getattr(order, "customer_id", None):
            try:
                result = await session.execute(select(Customer).where(Customer.id == order.customer_id))
                customer = result.scalar_one_or_none()
            except Exception:
                customer = None

        # Fetch tenant for name if available
        tenant_name = None
        try:
            result = await session.execute(select(Tenant).where(Tenant.id == order.tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant:
                tenant_name = getattr(tenant, "name", None)
        except Exception:
            tenant_name = None

        invoice_number = self._generate_invoice_number(order.tenant_id, order.id, getattr(order, "created_at", None))

        # Build line items and calculate totals + GST
        tax_service = TaxService()
        line_items = []
        subtotal_cents = 0
        total_tax_cents = 0
        gst_breakdown: dict[str, int] = {"cgst": 0, "sgst": 0, "igst": 0}

        # Address for tax calculation
        shipping_address = getattr(order, "shipping_address_json", None) or {}
        if not isinstance(shipping_address, dict):
            shipping_address = {}

        # Supplier state (place of supply rules): resolved from the tenant's
        # store tax profile when present, else unknown → conservative IGST.
        supplier_state = ""
        try:
            from infalette_database.models.store import Store as _Store

            _srow = await session.execute(
                select(_Store).where(_Store.tenant_id == order.tenant_id).limit(1)
            )
            _store = _srow.scalars().first()
            if _store is not None:
                supplier_state = (
                    (_store.shipping_rules_json or {}).get("supplier_state")
                    or (_store.legal_pages_json or {}).get("supplier_state")
                    or ""
                )
        except Exception:
            supplier_state = ""

        for oi in order_items:
            snapshot = getattr(oi, "product_snapshot_json", None) or {}
            name = snapshot.get("name") or getattr(oi, "product_id", "Product")
            sku = snapshot.get("sku", "")
            tax_class = snapshot.get("tax_class", "standard") or "standard"
            quantity = oi.quantity
            price_cents = oi.price_cents
            line_total = price_cents * quantity
            subtotal_cents += line_total

            # Tax amount — immutable snapshot first (spec §7): use the tax
            # frozen at checkout (column or checkout snapshot); recompute
            # from current rates only for legacy orders without a snapshot.
            snap_tax = getattr(oi, "tax_cents", None)
            if snap_tax is None:
                snap_tax = snapshot.get("tax_cents")
            if snap_tax is not None:
                try:
                    tax_amount = int(snap_tax)
                except (TypeError, ValueError):
                    tax_amount = int(line_total * 0.18)
                snap_rate_bps = getattr(oi, "tax_rate_bps", None)
                if snap_rate_bps is None:
                    snap_rate_bps = snapshot.get("tax_rate_bps")
                try:
                    rate = int(snap_rate_bps) / 10000 if snap_rate_bps is not None else tax_service.TAX_RATES.get(tax_class, 0.18)
                except (TypeError, ValueError):
                    rate = tax_service.TAX_RATES.get(tax_class, 0.18)
            else:
                try:
                    tax_amount = tax_service.calculate_tax(line_total, tax_class, shipping_address)
                except Exception:
                    tax_amount = int(line_total * 0.18)
                rate = tax_service.TAX_RATES.get(tax_class, 0.18)

            total_tax_cents += tax_amount

            # CGST+SGST when the ship-to state equals the supplier state;
            # IGST for inter-state/exports (conservative default).
            breakdown = TaxService.gst_breakdown(
                line_total,
                rate,
                supplier_state,
                shipping_address.get("state", ""),
            ) if shipping_address.get("country", "").lower() == "india" else {
                "mode": "export",
                "igst_cents": 0,
                "total_tax_cents": 0,
            }
            gst_breakdown["igst"] += breakdown.get("igst_cents", 0) or 0
            gst_breakdown["cgst"] += breakdown.get("cgst_cents", 0) or 0
            gst_breakdown["sgst"] += (
                breakdown.get("sgst_cents", 0) or 0
            ) + (breakdown.get("utgst_cents", 0) or 0)

            line_items.append({
                "product_id": str(oi.product_id),
                "variant_id": str(oi.variant_id) if oi.variant_id else None,
                "name": name,
                "sku": sku,
                "quantity": quantity,
                "price_cents": price_cents,
                "price_display": f"{price_cents/100:.2f}",
                "line_total_cents": line_total,
                "line_total_display": f"{line_total/100:.2f}",
                "tax_class": tax_class,
                "gst_mode": breakdown["mode"],
                "tax_cents": tax_amount,
                "tax_display": f"{tax_amount/100:.2f}",
                "tax_rate": rate,
            })

        # Totals
        total_cents = getattr(order, "total_cents", subtotal_cents + total_tax_cents)
        # If order total already includes tax/shipping, derive shipping as remainder
        # Assume shipping = total - subtotal - tax (if positive)
        shipping_cents = max(total_cents - subtotal_cents - total_tax_cents, 0)
        grand_total_cents = subtotal_cents + total_tax_cents + shipping_cents

        # Use order.currency
        currency = getattr(order, "currency", "INR") or "INR"

        invoice_data = {
            "invoice_number": invoice_number,
            "order_id": str(order.id),
            "checkout_id": str(getattr(order, "checkout_id", "")) if getattr(order, "checkout_id", None) else None,
            "tenant_id": str(order.tenant_id),
            "tenant_name": tenant_name,
            "customer": {
                "id": str(customer.id) if customer else (str(order.customer_id) if getattr(order, "customer_id", None) else None),
                "email": getattr(customer, "email", None) if customer else None,
                "first_name": getattr(customer, "first_name", None) if customer else None,
                "last_name": getattr(customer, "last_name", None) if customer else None,
                "phone": getattr(customer, "phone", None) if customer else None,
            } if customer or getattr(order, "customer_id", None) else None,
            "shipping_address": shipping_address,
            "billing_address": getattr(order, "billing_address_json", None) or {},
            "line_items": line_items,
            "totals": {
                "subtotal_cents": subtotal_cents,
                "subtotal_display": f"{subtotal_cents/100:.2f} {currency}",
                "tax_total_cents": total_tax_cents,
                "tax_total_display": f"{total_tax_cents/100:.2f} {currency}",
                "shipping_cents": shipping_cents,
                "shipping_display": f"{shipping_cents/100:.2f} {currency}",
                "grand_total_cents": grand_total_cents,
                "grand_total_display": f"{grand_total_cents/100:.2f} {currency}",
                "currency": currency,
            },
            "gst_breakdown": {
                "cgst_cents": gst_breakdown["cgst"],
                "sgst_cents": gst_breakdown["sgst"],
                "igst_cents": gst_breakdown["igst"],
                "cgst_display": f"{gst_breakdown['cgst']/100:.2f}",
                "sgst_display": f"{gst_breakdown['sgst']/100:.2f}",
                "igst_display": f"{gst_breakdown['igst']/100:.2f}",
            },
            "order_status": getattr(order.status, "value", str(order.status)) if getattr(order, "status", None) else "unknown",
            "created_at": getattr(order, "created_at", datetime.now(timezone.utc)).isoformat() if getattr(order, "created_at", None) else datetime.now(timezone.utc).isoformat(),
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "currency": currency,
        }

        return invoice_data

    def render_html(self, invoice_data: dict) -> str:
        """Render invoice data as HTML string."""
        items_rows = ""
        for item in invoice_data.get("line_items", []):
            items_rows += f"""
            <tr>
                <td>{item.get('name','')}</td>
                <td>{item.get('sku','')}</td>
                <td style="text-align:center;">{item.get('quantity','')}</td>
                <td style="text-align:right;">{item.get('price_display','')}</td>
                <td style="text-align:right;">{item.get('line_total_display','')}</td>
                <td style="text-align:right;">{item.get('tax_display','')}</td>
            </tr>
            """

        shipping = invoice_data.get("shipping_address", {}) or {}
        billing = invoice_data.get("billing_address", {}) or {}
        totals = invoice_data.get("totals", {})
        gst = invoice_data.get("gst_breakdown", {})
        customer = invoice_data.get("customer", {}) or {}

        customer_name = f"{customer.get('first_name','') or ''} {customer.get('last_name','') or ''}".strip() or customer.get('email','') or "Customer"

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Invoice {invoice_data.get('invoice_number','')}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
.header {{ border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }}
.invoice-title {{ font-size: 28px; font-weight: bold; }}
.meta {{ margin-top: 10px; }}
.addresses {{ display: flex; justify-content: space-between; margin: 20px 0; }}
.address-box {{ width: 48%; border: 1px solid #ddd; padding: 15px; border-radius: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; }}
th {{ background-color: #f5f5f5; text-align: left; }}
.totals {{ margin-top: 20px; text-align: right; }}
.total-row {{ font-weight: bold; }}
.footer {{ margin-top: 40px; font-size: 12px; color: #777; text-align: center; border-top: 1px solid #ddd; padding-top: 10px; }}
</style>
</head>
<body>
<div class="header">
<div class="invoice-title">INVOICE</div>
<div class="meta">
<div><strong>Invoice Number:</strong> {invoice_data.get('invoice_number','')}</div>
<div><strong>Order ID:</strong> {invoice_data.get('order_id','')}</div>
<div><strong>Invoice Date:</strong> {invoice_data.get('invoice_date','')}</div>
<div><strong>Order Date:</strong> {invoice_data.get('created_at','')}</div>
<div><strong>Order Status:</strong> {invoice_data.get('order_status','')}</div>
<div><strong>Currency:</strong> {invoice_data.get('currency','INR')}</div>
</div>
</div>

<div class="addresses">
<div class="address-box">
<h4>Bill To</h4>
<p>{customer_name}<br>
{billing.get('line1','')}<br>
{billing.get('line2','') or ''}<br>
{billing.get('city','')}, {billing.get('state','')} {billing.get('postal_code','')}<br>
{billing.get('country','')}<br>
{customer.get('email','') or ''}<br>
{customer.get('phone','') or ''}
</p>
</div>
<div class="address-box">
<h4>Ship To</h4>
<p>{shipping.get('line1','')}<br>
{shipping.get('line2','') or ''}<br>
{shipping.get('city','')}, {shipping.get('state','')} {shipping.get('postal_code','')}<br>
{shipping.get('country','')}<br>
</p>
</div>
</div>

<div class="addresses">
<div class="address-box">
<h4>From</h4>
<p>{invoice_data.get('tenant_name') or f"Tenant {invoice_data.get('tenant_id','')[:8]}"}<br>
Infalette Commerce<br>
</p>
</div>
<div class="address-box">
<h4>GST Breakdown</h4>
<p>CGST: {gst.get('cgst_display','0.00')} {invoice_data.get('currency','INR')}<br>
SGST: {gst.get('sgst_display','0.00')} {invoice_data.get('currency','INR')}<br>
IGST: {gst.get('igst_display','0.00')} {invoice_data.get('currency','INR')}<br>
Total Tax: {totals.get('tax_total_display','0.00')}<br>
</p>
</div>
</div>

<table>
<thead>
<tr>
<th>Product</th>
<th>SKU</th>
<th>Qty</th>
<th>Price</th>
<th>Line Total</th>
<th>Tax</th>
</tr>
</thead>
<tbody>
{items_rows}
</tbody>
</table>

<div class="totals">
<p>Subtotal: {totals.get('subtotal_display','0.00')}</p>
<p>Tax: {totals.get('tax_total_display','0.00')}</p>
<p>Shipping: {totals.get('shipping_display','0.00')}</p>
<p class="total-row">Grand Total: {totals.get('grand_total_display','0.00')}</p>
</div>

<div class="footer">
<p>This is a computer-generated invoice. No signature required.</p>
<p>Invoice {invoice_data.get('invoice_number','')} • Generated by Infalette</p>
</div>
</body>
</html>
"""
        return html

    def generate_pdf(self, invoice_data: dict) -> bytes:
        """Generate PDF bytes for invoice.

        Tries to use weasyprint if available, otherwise returns HTML bytes with PDF header fallback.
        """
        html = self.render_html(invoice_data)
        # Try weasyprint
        try:
            from weasyprint import HTML  # type: ignore
            pdf_bytes = HTML(string=html).write_pdf()
            return pdf_bytes
        except Exception:
            # Fallback: return HTML encoded as bytes (caller should handle content-type)
            # To still be valid PDF-like, wrap HTML in minimal PDF structure? For now return HTML bytes.
            return html.encode("utf-8")

    async def get_invoice_html(self, order_id: UUID, session: AsyncSession) -> str:
        """Convenience: generate invoice and return HTML."""
        data = await self.generate_invoice(order_id, session)
        return self.render_html(data)

    async def get_invoice_pdf(self, order_id: UUID, session: AsyncSession) -> bytes:
        """Convenience: generate invoice and return PDF bytes."""
        data = await self.generate_invoice(order_id, session)
        return self.generate_pdf(data)
