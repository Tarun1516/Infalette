"""Integration tests for the checkout flow.

Fixed signatures for TaxService, ShippingService and expanded coverage:
discount code, inventory reserve/release, checkout creation.
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from infalette_commerce.cart import CartService
from infalette_commerce.tax import TaxService
from infalette_commerce.shipping import ShippingService
from infalette_commerce.discounts import DiscountService
from infalette_commerce.inventory import reserve_inventory, release_inventory, get_available_inventory
from infalette_database.models.product import Product
from infalette_database.models.discount_code import DiscountCode
from infalette_validation.schemas import CheckoutCreate, AddressSchema, CustomerDataSchema


@pytest.mark.asyncio
async def test_cart_service_get_or_create(db_session, tenant_id, customer_id):
    """Test cart creation."""
    service = CartService()
    cart = await service.get_or_create_cart(tenant_id, customer_id, db_session)
    assert cart is not None
    assert cart.tenant_id == tenant_id
    assert cart.customer_id == customer_id

    # Get same cart again
    cart2 = await service.get_or_create_cart(tenant_id, customer_id, db_session)
    assert cart2.id == cart.id


@pytest.mark.asyncio
async def test_tax_service_calculate():
    """GST slabs are product-class driven (not state driven)."""
    service = TaxService()
    tax = service.calculate_tax(10000, "standard", {"country": "India", "state": "Maharashtra"})
    assert tax == int(10000 * 0.18)
    # Same slab everywhere: state does not change the rate
    tax_other_state = service.calculate_tax(10000, "standard", {"country": "India", "state": "Madhya Pradesh"})
    assert tax_other_state == int(10000 * 0.18)
    # Reduced rate is chosen by product class
    tax_reduced = service.calculate_tax(10000, "reduced", {"country": "India", "state": "Maharashtra"})
    assert tax_reduced == int(10000 * 0.05)
    # Zero tax class
    tax_zero = service.calculate_tax(10000, "zero", {"country": "India", "state": "Maharashtra"})
    assert tax_zero == 0
    # Non-India address → standard 18%
    tax_us = service.calculate_tax(10000, "standard", {"country": "USA", "state": "California"})
    assert tax_us == 1800
    assert tax > 0


@pytest.mark.asyncio
async def test_shipping_service_calculate():
    """Test shipping calculation – fixed signature."""
    service = ShippingService()
    # Correct: calculate_shipping_cost(zone, weight_kg, order_total_cents, shipping_type)
    rate = service.calculate_shipping_cost(zone="Maharashtra", weight_kg=0.5, order_total_cents=10000, shipping_type="standard")
    assert rate == 10000  # standard base cost
    # Free shipping over 100000 cents (1000 INR)
    free = service.calculate_shipping_cost(zone="Maharashtra", weight_kg=0.5, order_total_cents=150000, shipping_type="standard")
    assert free == 0
    # Weight surcharge
    heavy = service.calculate_shipping_cost(zone="Maharashtra", weight_kg=3.0, order_total_cents=10000, shipping_type="standard")
    assert heavy == 10000 + int((3.0 - 2.0) * 500)
    assert rate >= 0
    # Options
    options = service.get_shipping_options(zone="default", weight_kg=1.0, order_total_cents=5000)
    assert len(options) == 3
    assert any(o["id"] == "express" for o in options)


@pytest.mark.asyncio
async def test_discount_service_apply_coupon():
    """Test discount application."""
    service = DiscountService()
    # Test percentage discount
    discounted = service.apply_coupon(10000, "percentage", 10)
    assert discounted == 9000

    # Test fixed discount
    discounted = service.apply_coupon(10000, "fixed", 500)
    assert discounted == 9500

    # Test fixed discount not below zero
    discounted = service.apply_coupon(300, "fixed", 500)
    assert discounted == 0

    # Test free shipping (no price change)
    assert service.apply_coupon(10000, "free_shipping", 0) == 10000

    # calculate_discount_amount
    assert service.calculate_discount_amount(10000, "percentage", 20) == 2000
    assert service.calculate_discount_amount(10000, "fixed", 1500) == 1500


@pytest.mark.asyncio
async def test_discount_code_validation_flow(db_session, tenant_id):
    """Test discount code validation with DB."""
    from sqlalchemy import select
    service = DiscountService()

    # Create a valid discount code
    code = f"TEST{uuid4().hex[:6].upper()}"
    discount = DiscountCode(
        tenant_id=tenant_id,
        code=code,
        discount_type="percentage",
        value=10,
        minimum_order_cents=5000,
        usage_limit=5,
        used_count=0,
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=10),
    )
    db_session.add(discount)
    await db_session.commit()
    await db_session.refresh(discount)

    # Valid coupon
    validation = await service.validate_coupon_code(code=code, tenant_id=tenant_id, order_total_cents=10000, session=db_session)
    assert validation["valid"] is True
    assert validation["type"] == "percentage"
    assert validation["value"] == 10

    # Apply coupon
    discounted = service.apply_coupon(10000, validation["type"], validation["value"])
    assert discounted == 9000

    # Below minimum should raise
    with pytest.raises(ValueError, match="Minimum order"):
        await service.validate_coupon_code(code=code, tenant_id=tenant_id, order_total_cents=1000, session=db_session)

    # Inactive coupon should raise
    discount.is_active = False
    await db_session.commit()
    with pytest.raises(ValueError, match="not active"):
        await service.validate_coupon_code(code=code, tenant_id=tenant_id, order_total_cents=10000, session=db_session)
    discount.is_active = True
    await db_session.commit()

    # Expired
    discount.expires_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()
    with pytest.raises(ValueError, match="expired"):
        await service.validate_coupon_code(code=code, tenant_id=tenant_id, order_total_cents=10000, session=db_session)
    discount.expires_at = datetime.utcnow() + timedelta(days=10)
    await db_session.commit()

    # Usage limit reached
    discount.used_count = 5
    await db_session.commit()
    with pytest.raises(ValueError, match="usage limit"):
        await service.validate_coupon_code(code=code, tenant_id=tenant_id, order_total_cents=10000, session=db_session)

    # Invalid code
    with pytest.raises(ValueError, match="Invalid coupon"):
        await service.validate_coupon_code(code="NONEXISTENT", tenant_id=tenant_id, order_total_cents=10000, session=db_session)

    # Check coupon validity helper
    discount.used_count = 0
    await db_session.commit()
    assert service.check_coupon_validity(discount, 10000) is True
    discount.is_active = False
    assert service.check_coupon_validity(discount, 10000) is False
    discount.is_active = True

    # Increment usage
    discount.used_count = 0
    await db_session.commit()
    await service.increment_usage_count(discount.id, db_session)
    await db_session.refresh(discount)
    assert discount.used_count == 1


@pytest.mark.asyncio
async def test_inventory_reserve_and_release(db_session, tenant_id):
    """Test inventory reserve/release flow."""
    # Create product
    product = Product(
        tenant_id=tenant_id,
        name="Test Product",
        slug=f"test-product-{uuid4().hex[:6]}",
        sku=f"SKU-{uuid4().hex[:8]}",
        price_cents=1000,
        inventory_quantity=10,
        inventory_track=True,
        inventory_policy="deny",
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    # Check available
    avail = await get_available_inventory(product.id, db_session)
    assert avail == 10

    # Reserve 3
    ok = await reserve_inventory(product.id, 3, db_session)
    assert ok is True
    avail = await get_available_inventory(product.id, db_session)
    assert avail == 7

    # Reserve more than available should fail
    ok = await reserve_inventory(product.id, 8, db_session)
    assert ok is False
    # Available unchanged
    avail = await get_available_inventory(product.id, db_session)
    assert avail == 7

    # Release 2
    await release_inventory(product.id, 2, db_session)
    avail = await get_available_inventory(product.id, db_session)
    assert avail == 9

    # Reserve with sufficient inventory again
    ok = await reserve_inventory(product.id, 9, db_session)
    assert ok is True
    avail = await get_available_inventory(product.id, db_session)
    assert avail == 0

    # Test inventory_track=False always allows reserve
    product2 = Product(
        tenant_id=tenant_id,
        name="Untracked",
        slug=f"untracked-{uuid4().hex[:6]}",
        sku=f"SKU-UNTR-{uuid4().hex[:8]}",
        price_cents=500,
        inventory_quantity=0,
        inventory_track=False,
    )
    db_session.add(product2)
    await db_session.commit()
    await db_session.refresh(product2)
    ok = await reserve_inventory(product2.id, 100, db_session)
    assert ok is True

    # Test inventory_policy continue allows negative
    product3 = Product(
        tenant_id=tenant_id,
        name="Continue Policy",
        slug=f"continue-{uuid4().hex[:6]}",
        sku=f"SKU-CONT-{uuid4().hex[:8]}",
        price_cents=500,
        inventory_quantity=2,
        inventory_track=True,
        inventory_policy="continue",
    )
    db_session.add(product3)
    await db_session.commit()
    await db_session.refresh(product3)
    ok = await reserve_inventory(product3.id, 5, db_session)
    assert ok is True
    avail = await get_available_inventory(product3.id, db_session)
    assert avail == -3  # allowed to go negative with continue policy


@pytest.mark.asyncio
async def test_checkout_creation_flow(db_session, tenant_id, customer_id):
    """Test checkout creation with tax, shipping, inventory."""
    from infalette_commerce.checkout import CheckoutService
    from infalette_database.models.customer import Customer
    from infalette_database.models.cart import Cart
    from infalette_database.models.cart_item import CartItem

    # Create customer
    customer = Customer(
        tenant_id=tenant_id,
        email=f"test-{uuid4().hex[:6]}@example.com",
        first_name="Test",
        last_name="User",
        phone="9999999999",
        status="active",
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    # Create products
    p1 = Product(
        tenant_id=tenant_id,
        name="Product A",
        slug=f"product-a-{uuid4().hex[:6]}",
        sku=f"SKU-A-{uuid4().hex[:8]}",
        price_cents=2000,
        sale_price_cents=None,
        tax_class="standard",
        inventory_quantity=20,
    )
    p2 = Product(
        tenant_id=tenant_id,
        name="Product B",
        slug=f"product-b-{uuid4().hex[:6]}",
        sku=f"SKU-B-{uuid4().hex[:8]}",
        price_cents=1500,
        sale_price_cents=1200,  # sale price should be used
        tax_class="reduced",
        inventory_quantity=15,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()
    await db_session.refresh(p1)
    await db_session.refresh(p2)

    # Create cart with items
    cart = Cart(tenant_id=tenant_id, customer_id=customer.id, total_cents=0)
    db_session.add(cart)
    await db_session.commit()
    await db_session.refresh(cart)

    ci1 = CartItem(cart_id=cart.id, product_id=p1.id, quantity=2, price_cents=p1.price_cents)
    ci2 = CartItem(cart_id=cart.id, product_id=p2.id, quantity=1, price_cents=p2.sale_price_cents or p2.price_cents)
    db_session.add_all([ci1, ci2])
    await db_session.commit()

    # Create discount code
    code = f"DISC{uuid4().hex[:4].upper()}"
    discount = DiscountCode(
        tenant_id=tenant_id,
        code=code,
        discount_type="percentage",
        value=10,
        minimum_order_cents=0,
        usage_limit=10,
        used_count=0,
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=5),
    )
    db_session.add(discount)
    await db_session.commit()

    # Build checkout data
    addr = AddressSchema(line1="123 Test St", line2=None, city="Mumbai", state="Maharashtra", postal_code="400001", country="India")
    customer_data = CustomerDataSchema(email=customer.email, first_name="Test", last_name="User", phone="9999999999")
    data = CheckoutCreate(customer_data=customer_data, shipping_address=addr, billing_address=addr, discount_codes=[code])

    svc = CheckoutService()
    checkout = await svc.create_checkout(tenant_id, customer.id, data, db_session)

    assert checkout is not None
    assert checkout.tenant_id == tenant_id
    assert checkout.total_cents > 0
    # Subtotal before tax/shipping/discount: (2000*2) + (1200*1)=5200. Discount 10% => 4680, + tax etc >0
    assert checkout.status.value == "pending"
    assert len(checkout.items_json) == 2

    # Checkout creation should reserve inventory
    avail_p1 = await get_available_inventory(p1.id, db_session)
    # originally 20, reserved 2 → 18
    assert avail_p1 == 18


@pytest.mark.asyncio
async def test_checkout_cod_flow(db_session, tenant_id, customer_id):
    """Test COD checkout creates order without payment provider."""
    from infalette_commerce.checkout import CheckoutService
    from infalette_database.models.customer import Customer
    from infalette_database.models.cart import Cart
    from infalette_database.models.cart_item import CartItem

    customer = Customer(
        tenant_id=tenant_id,
        email=f"cod-{uuid4().hex[:6]}@example.com",
        first_name="COD",
        last_name="Tester",
        phone="8888888888",
        status="active",
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    product = Product(
        tenant_id=tenant_id,
        name="COD Product",
        slug=f"cod-product-{uuid4().hex[:6]}",
        sku=f"SKU-COD-{uuid4().hex[:8]}",
        price_cents=3000,
        inventory_quantity=10,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    cart = Cart(tenant_id=tenant_id, customer_id=customer.id, total_cents=0)
    db_session.add(cart)
    await db_session.commit()
    await db_session.refresh(cart)
    ci = CartItem(cart_id=cart.id, product_id=product.id, quantity=1, price_cents=product.price_cents)
    db_session.add(ci)
    await db_session.commit()

    addr = AddressSchema(line1="456 COD St", city="Delhi", state="Delhi", postal_code="110001", country="India")
    cd = CustomerDataSchema(email=customer.email, first_name="COD", last_name="Tester", phone="8888888888")
    data = CheckoutCreate(customer_data=cd, shipping_address=addr, billing_address=addr)
    svc = CheckoutService()
    checkout = await svc.create_checkout(tenant_id, customer.id, data, db_session)

    # Initiate COD payment
    result = await svc.initiate_payment(tenant_id, checkout.id, "cod", db_session)
    assert result["provider"] == "cod"
    assert result["cod"] is True
    assert "order_id" in result

    # Verify order exists
    from infalette_commerce.orders import OrderService
    osvc = OrderService()
    order = await osvc.get_order(tenant_id, result["order_id"], db_session) if isinstance(result["order_id"], UUID) else await osvc.get_order(tenant_id, UUID(result["order_id"]), db_session)
    assert order is not None
    assert order.status.value == "confirmed"

    # Verify payment record with COD provider
    from sqlalchemy import select
    from infalette_database.models.payment import Payment, PaymentProvider
    res = await db_session.execute(select(Payment).where(Payment.order_id == order.id))
    payment = res.scalar_one_or_none()
    assert payment is not None
    assert payment.provider == PaymentProvider.COD
