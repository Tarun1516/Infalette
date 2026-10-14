"""Unit tests for checkout service and invoice."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from infalette_commerce.tax import TaxService
from infalette_commerce.shipping import ShippingService
from infalette_commerce.invoice import InvoiceService


def test_checkout_tax_shipping_integration():
    # Pure checkout total logic without DB: subtotal + tax + shipping
    tax_svc = TaxService()
    ship_svc = ShippingService()
    subtotal = 5000
    tax = tax_svc.calculate_tax(subtotal, "standard", {"country": "India", "state": "Maharashtra"})
    shipping = ship_svc.calculate_shipping_cost(zone="Maharashtra", weight_kg=1.0, order_total_cents=subtotal+tax, shipping_type="standard")
    total = subtotal + tax + shipping
    assert tax == 900
    assert shipping == 10000  # under threshold
    assert total == 15900

    # Over free shipping threshold
    subtotal_big = 100000
    tax_big = tax_svc.calculate_tax(subtotal_big, "standard", {"country": "India", "state": "Maharashtra"})
    shipping_big = ship_svc.calculate_shipping_cost(zone="Mumbai", weight_kg=1.0, order_total_cents=subtotal_big+tax_big, shipping_type="standard")
    assert shipping_big == 0


@pytest.mark.asyncio
async def test_invoice_service_generate_number():
    svc = InvoiceService()
    tenant_id = uuid4()
    order_id = uuid4()
    now = datetime(2026, 3, 15, tzinfo=timezone.utc)
    num = svc._generate_invoice_number(tenant_id, order_id, now)
    assert num.startswith("INV-")
    assert str(now.year) in num
    assert len(num.split("-")) == 4
    # deterministic
    num2 = svc._generate_invoice_number(tenant_id, order_id, now)
    assert num == num2
    # different order id gives different number
    num3 = svc._generate_invoice_number(tenant_id, uuid4(), now)
    assert num != num3


def test_invoice_render_html():
    svc = InvoiceService()
    data = {
        "invoice_number": "INV-TEST-2026-000001",
        "order_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "tenant_name": "Test Store",
        "customer": {"first_name": "John", "last_name": "Doe", "email": "john@example.com", "phone": "123"},
        "shipping_address": {"line1": "123 St", "city": "Mumbai", "state": "MH", "postal_code": "400001", "country": "India"},
        "billing_address": {"line1": "123 St", "city": "Mumbai", "state": "MH", "postal_code": "400001", "country": "India"},
        "line_items": [
            {"name": "Product A", "sku": "SKU-A", "quantity": 2, "price_display": "10.00", "line_total_display": "20.00", "tax_display": "3.60"},
        ],
        "totals": {"subtotal_display": "20.00 INR", "tax_total_display": "3.60 INR", "shipping_display": "10.00 INR", "grand_total_display": "33.60 INR"},
        "gst_breakdown": {"cgst_display": "1.80", "sgst_display": "1.80", "igst_display": "0.00"},
        "order_status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "invoice_date": datetime.now(timezone.utc).isoformat(),
        "currency": "INR",
    }
    html = svc.render_html(data)
    assert "INV-TEST-2026-000001" in html
    assert "Product A" in html
    assert "John Doe" in html or "john@example.com" in html
    assert "<html>" in html.lower()


def test_invoice_generate_pdf_fallback():
    svc = InvoiceService()
    data = {
        "invoice_number": "INV-TEST-2026-000002",
        "order_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "tenant_name": "Test Store",
        "customer": None,
        "shipping_address": {},
        "billing_address": {},
        "line_items": [],
        "totals": {"subtotal_display": "0.00", "tax_total_display": "0.00", "shipping_display": "0.00", "grand_total_display": "0.00"},
        "gst_breakdown": {"cgst_display": "0.00", "sgst_display": "0.00", "igst_display": "0.00"},
        "order_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "invoice_date": datetime.now(timezone.utc).isoformat(),
        "currency": "INR",
    }
    pdf_bytes = svc.generate_pdf(data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # If weasyprint not installed, it returns HTML bytes containing invoice number
    assert b"INV-TEST" in pdf_bytes or pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_invoice_generate_with_mock_db():
    svc = InvoiceService()
    order_id = uuid4()
    tenant_id = uuid4()
    # Mock Order, OrderItem, etc.
    mock_order = MagicMock()
    mock_order.id = order_id
    mock_order.tenant_id = tenant_id
    mock_order.customer_id = None
    mock_order.total_cents = 5000
    mock_order.currency = "INR"
    mock_order.status = MagicMock(value="confirmed")
    mock_order.status.value = "confirmed"
    mock_order.created_at = datetime.now(timezone.utc)
    mock_order.checkout_id = uuid4()
    mock_order.shipping_address_json = {"line1": "123 St", "city": "Mumbai", "state": "Maharashtra", "country": "India", "postal_code": "400001"}
    mock_order.billing_address_json = {"line1": "123 St", "city": "Mumbai", "state": "Maharashtra", "country": "India", "postal_code": "400001"}

    mock_item = MagicMock()
    mock_item.order_id = order_id
    mock_item.product_id = uuid4()
    mock_item.variant_id = None
    mock_item.quantity = 2
    mock_item.price_cents = 1500
    mock_item.product_snapshot_json = {"name": "Mock Product", "sku": "MOCK-1", "tax_class": "standard"}

    mock_session = AsyncMock()
    # Configure execute to return different results based on model
    def fake_execute(stmt):
        # Determine what is being selected via string inspection is fragile; instead we rely on order of calls
        # We'll use side_effect list
        # This is handled via side_effect assignment outside
        raise NotImplementedError

    # Setup side effects in order: Order, OrderItems, Customer (None), Tenant (None)
    mock_order_result = MagicMock()
    mock_order_result.scalar_one_or_none.return_value = mock_order
    mock_items_result = MagicMock()
    mock_items_result.scalars.return_value.all.return_value = [mock_item]
    mock_customer_result = MagicMock()
    mock_customer_result.scalar_one_or_none.return_value = None
    mock_tenant_result = MagicMock()
    mock_tenant_result.scalar_one_or_none.return_value = None

    mock_session.execute = AsyncMock(side_effect=[mock_order_result, mock_items_result, mock_customer_result, mock_tenant_result])

    data = await svc.generate_invoice(order_id, mock_session)
    assert data["invoice_number"].startswith("INV-")
    assert data["order_id"] == str(order_id)
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["quantity"] == 2
    assert data["totals"]["grand_total_cents"] >= 3000
    assert "gst_breakdown" in data


@pytest.mark.asyncio
async def test_checkout_cod_initiate_mocked():
    from infalette_commerce.checkout import CheckoutService
    tenant_id = uuid4()
    checkout_id = uuid4()
    customer_id = uuid4()

    # Mock checkout
    mock_checkout = MagicMock()
    mock_checkout.id = checkout_id
    mock_checkout.tenant_id = tenant_id
    mock_checkout.customer_id = customer_id
    mock_checkout.total_cents = 5000
    mock_checkout.currency = "INR"
    mock_checkout.status = MagicMock()
    mock_checkout.status.value = "pending"
    # Compare with CheckoutStatus.PENDING - mock needs equality check via !=
    # We'll patch CheckoutStatus.PENDING check by making mock status equal to PENDING
    from infalette_database.models.checkout import CheckoutStatus
    mock_checkout.status = CheckoutStatus.PENDING

    mock_session = AsyncMock()

    # For COD flow, service will:
    # 1. select checkout
    # 2. execute update checkout status
    # 3. flush payment
    # 4. execute update again for _confirm? Actually _confirm_checkout does select checkout, update to PAID, add order, etc.
    # Simplify: we will mock entire _confirm_checkout to return fake order
    fake_order = MagicMock()
    fake_order.id = uuid4()
    fake_order.status = MagicMock(value="confirmed")
    fake_order.status.value = "confirmed"

    mock_checkout_result = MagicMock()
    mock_checkout_result.scalar_one_or_none.return_value = mock_checkout

    mock_session.execute = AsyncMock(return_value=mock_checkout_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()

    svc = CheckoutService()
    with patch.object(svc, "_confirm_checkout", new=AsyncMock(return_value=fake_order)):
        with patch("infalette_commerce.checkout.record_event", new=AsyncMock()):
            result = await svc.initiate_payment(tenant_id, checkout_id, "cod", mock_session)
            assert result["provider"] == "cod"
            assert result["cod"] is True
            assert "order_id" in result
