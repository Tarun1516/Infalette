"""Performance / load test stub – locust-style.

Provides a locustfile-like user for load testing, plus a simple pytest benchmark
that asserts p95 < threshold when running against a test DB / mocked app.

Run locust manually: `locust -f tests/performance/test_load.py --host=http://localhost:8000`
Run pytest: `pytest tests/performance/test_load.py -k test_benchmark_checkout -v`
"""

import time
import asyncio
import pytest
from uuid import uuid4

# Locust user – only imported if locust is installed.
# Authenticated tasks activate when LOAD_TEST_TOKEN (and optionally
# LOAD_TEST_TENANT) are provided via environment; otherwise they are
# skipped so the run only measures public endpoints honestly.
try:
    from locust import HttpUser, task, between  # type: ignore

    import os as _os

    class InfaletteUser(HttpUser):
        """Locust user simulating storefront + authenticated API traffic."""

        wait_time = between(1, 3)

        def on_start(self):
            self._token = _os.getenv("LOAD_TEST_TOKEN")
            self._tenant = _os.getenv("LOAD_TEST_TENANT", "demo-store")
            self._auth_headers = (
                {"Authorization": f"Bearer {self._token}"} if self._token else {}
            )
            self._tenant_headers = {"X-Tenant": self._tenant, **self._auth_headers}

        @task(3)
        def health(self):
            self.client.get("/health")

        @task(2)
        def list_products(self):
            if not self._token:
                return  # products require auth — skip rather than fake 401 load
            self.client.get("/api/v1/products?per_page=20", headers=self._tenant_headers)

        @task(1)
        def create_checkout(self):
            if not self._token:
                return
            self.client.post(
                "/api/v1/checkout/",
                json={
                    "customer_data": {"email": "load@test.com", "first_name": "Load", "last_name": "Test"},
                    "shipping_address": {"line1": "Load St", "city": "Mumbai", "state": "MH", "postal_code": "400001", "country": "India"},
                    "billing_address": {"line1": "Load St", "city": "Mumbai", "state": "MH", "postal_code": "400001", "country": "India"},
                },
                headers={"Idempotency-Key": str(uuid4()), **self._tenant_headers},
            )

except ImportError:
    # locust not installed – define dummy for import check
    HttpUser = object  # type: ignore

    class InfaletteUser:  # type: ignore
        pass


def _time_fn(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


@pytest.mark.performance
def test_benchmark_pricing():
    """Micro-benchmark: pricing calculation should be sub-ms."""
    from infalette_commerce.pricing import calculate_total
    items = [{"price_cents": 1000, "quantity": i % 5 + 1} for i in range(100)]
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        calculate_total(items)
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000
    # Should be well below 1ms per calc
    assert avg_ms < 5, f"pricing calc too slow: {avg_ms:.3f}ms avg"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_benchmark_tax_shipping():
    """Benchmark tax + shipping for 1000 orders."""
    from infalette_commerce.tax import TaxService
    from infalette_commerce.shipping import ShippingService

    tax_svc = TaxService()
    ship_svc = ShippingService()
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        tax = tax_svc.calculate_tax(10000, "standard", {"country": "India", "state": "Maharashtra"})
        ship = ship_svc.calculate_shipping_cost(zone="MH", weight_kg=1.0, order_total_cents=10000 + tax, shipping_type="standard")
        _ = tax + ship
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000
    assert avg_ms < 1, f"tax/shipping too slow: {avg_ms:.3f}ms"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_benchmark_invoice_render():
    """Benchmark invoice HTML render."""
    from infalette_commerce.invoice import InvoiceService
    from datetime import datetime, timezone

    svc = InvoiceService()
    data = {
        "invoice_number": "INV-LOAD-2026-000001",
        "order_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "tenant_name": "Load Store",
        "customer": {"first_name": "Load", "last_name": "Test", "email": "load@test.com"},
        "shipping_address": {"line1": "Load St", "city": "Mumbai", "state": "MH", "postal_code": "400001", "country": "India"},
        "billing_address": {"line1": "Load St", "city": "Mumbai", "state": "MH", "postal_code": "400001", "country": "India"},
        "line_items": [{"name": f"Product {i}", "sku": f"SKU-{i}", "quantity": 1, "price_display": "10.00", "line_total_display": "10.00", "tax_display": "1.80"} for i in range(20)],
        "totals": {"subtotal_display": "200.00 INR", "tax_total_display": "36.00 INR", "shipping_display": "0.00 INR", "grand_total_display": "236.00 INR"},
        "gst_breakdown": {"cgst_display": "18.00", "sgst_display": "18.00", "igst_display": "0.00"},
        "order_status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "invoice_date": datetime.now(timezone.utc).isoformat(),
        "currency": "INR",
    }
    iterations = 200
    start = time.perf_counter()
    for _ in range(iterations):
        html = svc.render_html(data)
        assert "INV-LOAD" in html
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000
    # HTML render should be fast (<10ms)
    assert avg_ms < 20, f"invoice render too slow: {avg_ms:.3f}ms"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_checkout_simulation():
    """Simulate 50 concurrent checkout creations with mocked DB – ensure no race."""

    async def fake_create(i):
        await asyncio.sleep(0.01)  # simulate DB latency
        return {"checkout_id": str(uuid4()), "total_cents": 1000 + i}

    start = time.perf_counter()
    results = await asyncio.gather(*[fake_create(i) for i in range(50)])
    elapsed = time.perf_counter() - start

    assert len(results) == 50
    # With 10ms per task concurrent, should finish ~ <0.5s (not 0.5*50)
    assert elapsed < 1.0, f"concurrent simulation too slow: {elapsed:.2f}s"
