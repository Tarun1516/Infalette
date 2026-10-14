"""Unit tests for pricing, tax, shipping logic."""

import pytest
from infalette_commerce.pricing import calculate_price, apply_discount, calculate_total, calculate_tax
from infalette_commerce.tax import TaxService
from infalette_commerce.shipping import ShippingService
from infalette_commerce.discounts import DiscountService


def test_calculate_price():
    assert calculate_price(1000, 3) == 3000
    assert calculate_price(0, 10) == 0
    assert calculate_price(500, 0) == 0


def test_apply_discount():
    assert apply_discount(10000, 10) == 9000
    assert apply_discount(10000, 0) == 10000
    assert apply_discount(10000, 100) == 0
    assert apply_discount(10000, 50) == 5000


def test_calculate_total_no_discount():
    items = [{"price_cents": 2000, "quantity": 2}, {"price_cents": 1500, "quantity": 1}]
    assert calculate_total(items) == 5500
    assert calculate_total([]) == 0


def test_calculate_total_with_discount():
    items = [{"price_cents": 10000, "quantity": 1}]
    discounts = [{"percent": 10}]
    assert calculate_total(items, discounts) == 9000
    # Multiple discounts sequential
    discounts = [{"percent": 10}, {"percent": 10}]
    # 10000 -> 9000 -> 8100
    assert calculate_total(items, discounts) == 8100


def test_calculate_tax_function():
    assert calculate_tax(10000, 0.18) == 1800
    assert calculate_tax(10000, 0.05) == 500
    assert calculate_tax(10000, 0.0) == 0


def test_tax_service_rates():
    svc = TaxService()
    # Standard 18%
    assert svc.TAX_RATES["standard"] == 0.18
    assert svc.calculate_tax(10000, "standard", {"country": "USA"}) == 1800
    # GST slabs are product-class driven — state never changes the rate
    assert svc.calculate_tax(10000, "standard", {"country": "India", "state": "Madhya Pradesh"}) == 1800
    assert svc.calculate_tax(10000, "standard", {"country": "India", "state": "Rajasthan"}) == 1800
    assert svc.calculate_tax(10000, "standard", {"country": "India", "state": "Maharashtra"}) == 1800
    # Tenant flat override applies only when the product has no tax class
    assert svc.calculate_tax(10000, "", {}, store_override=12) == 1200
    assert svc.calculate_tax(10000, "standard", {}, store_override=12) == 1800
    # Zero / exempt
    assert svc.calculate_tax(10000, "zero", {"country": "India", "state": "Maharashtra"}) == 0
    assert svc.calculate_tax(10000, "exempt", {"country": "India"}) == 0
    # Unknown tax_class fallback to standard
    assert svc.calculate_tax(10000, "unknown_class", {"country": "India"}) == 1800
    # get_tax_rate
    assert svc.get_tax_rate("standard") == 0.18
    assert svc.get_tax_rate("reduced") == 0.05


def test_gst_breakdown_split():
    """Intra-state splits CGST/SGST; inter-state is IGST."""
    svc = TaxService()
    intra = svc.gst_breakdown(1000, 0.18, "Karnataka", "Karnataka")
    assert intra["mode"] == "intra_state"
    assert intra["cgst_cents"] + intra["sgst_cents"] == intra["total_tax_cents"]
    inter = svc.gst_breakdown(1000, 0.18, "Karnataka", "Delhi")
    assert inter["mode"] == "inter_state"
    assert inter["igst_cents"] == inter["total_tax_cents"]


def test_tax_service_apply_to_order():
    svc = TaxService()
    items = [
        {"price_cents": 1000, "quantity": 2, "tax_class": "standard", "product_id": "p1"},
        {"price_cents": 500, "quantity": 1, "tax_class": "zero", "product_id": "p2"},
    ]
    result = svc.apply_tax_to_order(items, {"country": "India", "state": "Maharashtra"})
    assert result["total_tax_cents"] == 360  # (2000*0.18)=360 + 0
    assert len(result["item_taxes"]) == 2
    assert svc.handle_tax_exempt_customers(None, 10000) == 1800
    # Tax exempt customer
    class FakeCust:
        tax_exempt = True
    assert svc.handle_tax_exempt_customers(FakeCust(), 10000) == 0


def test_shipping_service():
    svc = ShippingService()
    # Base cost standard
    assert svc.calculate_shipping_cost(zone="Mumbai", weight_kg=1.0, order_total_cents=5000, shipping_type="standard") == 10000
    # Express more expensive
    assert svc.calculate_shipping_cost(zone="Mumbai", weight_kg=1.0, order_total_cents=5000, shipping_type="express") == 20000
    # Free shipping threshold
    assert svc.calculate_shipping_cost(zone="Mumbai", weight_kg=1.0, order_total_cents=100000, shipping_type="standard") == 0
    assert svc.calculate_shipping_cost(zone="Mumbai", weight_kg=10, order_total_cents=100000, shipping_type="express") == 0
    # Weight surcharge
    assert svc.calculate_shipping_cost(zone="Mumbai", weight_kg=3.0, order_total_cents=5000, shipping_type="standard") == 10000 + 500
    assert svc.calculate_shipping_cost(zone="Mumbai", weight_kg=2.0, order_total_cents=5000, shipping_type="standard") == 10000
    # Options
    opts = svc.get_shipping_options(zone="Delhi", weight_kg=0.5, order_total_cents=5000)
    assert len(opts) == 3
    assert all("price_cents" in o for o in opts)
    # Address validation
    assert svc.validate_shipping_address({"line1": "A", "city": "C", "state": "S", "postal_code": "P", "country": "IN"}) is True
    assert svc.validate_shipping_address({"line1": "A", "city": "C"}) is False
    assert svc.validate_shipping_address({}) is False


def test_discount_service_pure():
    svc = DiscountService()
    # Percentage
    assert svc.apply_coupon(10000, "percentage", 25) == 7500
    # Fixed
    assert svc.apply_coupon(10000, "fixed", 3000) == 7000
    assert svc.apply_coupon(200, "fixed", 500) == 0
    # Free shipping
    assert svc.apply_coupon(10000, "free_shipping", 0) == 10000
    # Unknown type
    assert svc.apply_coupon(10000, "unknown", 10) == 10000
    # discount amount
    assert svc.calculate_discount_amount(10000, "percentage", 10) == 1000
    assert svc.calculate_discount_amount(10000, "fixed", 1500) == 1500
    assert svc.calculate_discount_amount(10000, "free_shipping", 0) == 0

    # check_coupon_validity with dummy object
    from datetime import datetime, timedelta
    class Dummy:
        def __init__(self):
            self.is_active = True
            self.expires_at = datetime.utcnow() + timedelta(days=1)
            self.usage_limit = 5
            self.used_count = 2
            self.minimum_order_cents = 1000

    d = Dummy()
    assert svc.check_coupon_validity(d, 5000) is True
    d.is_active = False
    assert svc.check_coupon_validity(d, 5000) is False
    d.is_active = True
    d.expires_at = datetime.utcnow() - timedelta(days=1)
    assert svc.check_coupon_validity(d, 5000) is False
    d.expires_at = datetime.utcnow() + timedelta(days=1)
    d.used_count = 5
    assert svc.check_coupon_validity(d, 5000) is False
    d.used_count = 2
    assert svc.check_coupon_validity(d, 500) is False  # below minimum
