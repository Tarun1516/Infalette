"""Unit tests for cart service (mocked DB) and pricing helpers."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from infalette_commerce.cart import CartService
from infalette_commerce.pricing import calculate_total


@pytest.mark.asyncio
async def test_cart_get_or_create_creates_new():
    svc = CartService()
    tenant_id = uuid4()
    customer_id = uuid4()

    mock_session = AsyncMock()
    # Mock select returns None -> creates new cart
    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result_none)
    # For add/commit/refresh, mock_cart
    fake_cart = MagicMock()
    fake_cart.id = uuid4()
    fake_cart.tenant_id = tenant_id
    fake_cart.customer_id = customer_id
    # Capture added object
    added = {}
    def add(obj):
        added["obj"] = obj
        obj.id = fake_cart.id
        obj.tenant_id = tenant_id
        obj.customer_id = customer_id
    mock_session.add = MagicMock(side_effect=add)
    mock_session.commit = AsyncMock()
    async def refresh(obj):
        obj.id = fake_cart.id
    mock_session.refresh = AsyncMock(side_effect=refresh)

    cart = await svc.get_or_create_cart(tenant_id, customer_id, mock_session)
    assert cart.id == fake_cart.id
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_cart_add_to_cart_existing_item():
    svc = CartService()
    tenant_id = uuid4()
    customer_id = uuid4()
    product_id = uuid4()

    mock_session = AsyncMock()

    # Mock get_or_create_cart to return fake cart
    fake_cart = MagicMock()
    fake_cart.id = uuid4()
    fake_cart.tenant_id = tenant_id

    existing_item = MagicMock()
    existing_item.cart_id = fake_cart.id
    existing_item.product_id = product_id
    existing_item.quantity = 2

    # Need to mock two selects: one for get_or_create, one for existing_item check
    # We'll patch get_or_create_cart
    with patch.object(svc, "get_or_create_cart", new=AsyncMock(return_value=fake_cart)):
        # Mock execute for existing item lookup
        mock_res_existing = MagicMock()
        mock_res_existing.scalar_one_or_none.return_value = existing_item
        mock_session.execute = AsyncMock(return_value=mock_res_existing)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        item = await svc.add_to_cart(tenant_id, customer_id, product_id, quantity=3, session=mock_session)
        assert item.quantity == 5  # 2+3
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_cart_calculate_total_logic():
    svc = CartService()
    cart_id = uuid4()
    mock_session = AsyncMock()

    # Mock CartItems
    item1 = MagicMock()
    item1.price_cents = 1000
    item1.quantity = 2
    item2 = MagicMock()
    item2.price_cents = 500
    item2.quantity = 3

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [item1, item2]
    mock_session.execute = AsyncMock(return_value=mock_res)
    mock_session.commit = AsyncMock()

    with patch("infalette_commerce.cart.calculate_total", return_value=3500) as mock_calc:
        total = await svc.calculate_cart_total(cart_id, mock_session)
        mock_calc.assert_called_once()
        assert total == 3500


def test_calculate_total_pricing_helper():
    items = [{"price_cents": 2000, "quantity": 1}, {"price_cents": 3000, "quantity": 2}]
    # Must pass list of dicts with price_cents and quantity for calculate_total
    # Our function expects items with dict keys
    assert calculate_total(items) == 8000
    assert calculate_total([]) == 0
    assert calculate_total(items, [{"percent": 10}]) == 7200


@pytest.mark.asyncio
async def test_cart_remove_and_clear():
    svc = CartService()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    # remove_from_cart should execute delete
    await svc.remove_from_cart(uuid4(), mock_session)
    assert mock_session.execute.called
    assert mock_session.commit.called

    mock_session.execute.reset_mock()
    mock_session.commit.reset_mock()
    await svc.clear_cart(uuid4(), mock_session)
    assert mock_session.execute.called
