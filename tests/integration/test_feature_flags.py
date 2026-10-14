"""Integration tests for feature flags and plan entitlements."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from apps.api.core.feature_flags import (
    Plan,
    Feature,
    PLAN_FEATURES,
    PLAN_QUOTAS,
    has_feature,
    get_plan_quota,
    normalize_plan,
    get_tenant_plan,
)


def test_has_feature_store_plan():
    assert has_feature(Plan.STORE, Feature.PRODUCTS) is True
    assert has_feature(Plan.STORE, Feature.ORDERS) is True
    assert has_feature(Plan.STORE, Feature.CART_CHECKOUT) is True
    assert has_feature(Plan.STORE, Feature.INSTAGRAM_AUTOMATION) is False
    assert has_feature(Plan.STORE, Feature.CUSTOMER_PROFILES) is False


def test_has_feature_automation_plan():
    assert has_feature(Plan.STORE_AUTOMATION, Feature.INSTAGRAM_AUTOMATION) is True
    assert has_feature(Plan.STORE_AUTOMATION, Feature.WHATSAPP_AUTOMATION) is True
    assert has_feature(Plan.STORE_AUTOMATION, Feature.FUNNEL_ANALYTICS) is True
    assert has_feature(Plan.STORE_AUTOMATION, Feature.CUSTOMER_PROFILES) is False  # only CRM
    assert has_feature(Plan.STORE_AUTOMATION, Feature.CSV_EXPORTS) is False


def test_has_feature_crm_plan_all():
    for feat in PLAN_FEATURES[Plan.STORE]:
        assert has_feature(Plan.STORE_AUTOMATION_CRM, feat) is True
    for feat in PLAN_FEATURES[Plan.STORE_AUTOMATION]:
        assert has_feature(Plan.STORE_AUTOMATION_CRM, feat) is True
    assert has_feature(Plan.STORE_AUTOMATION_CRM, Feature.CSV_EXPORTS) is True
    assert has_feature(Plan.STORE_AUTOMATION_CRM, Feature.ABANDONED_SEGMENTS) is True


def test_plan_quotas():
    assert get_plan_quota(Plan.STORE, "products") == 100
    assert get_plan_quota(Plan.STORE, "automations") == 0
    assert get_plan_quota(Plan.STORE_AUTOMATION, "products") == 500
    assert get_plan_quota(Plan.STORE_AUTOMATION_CRM, "products") is None  # unlimited
    assert get_plan_quota(Plan.STORE_AUTOMATION_CRM, "orders_per_month") is None


def test_normalize_plan():
    assert normalize_plan("store") == Plan.STORE
    assert normalize_plan("STORE") == Plan.STORE
    assert normalize_plan("basic") == Plan.STORE
    assert normalize_plan("store_automation") == Plan.STORE_AUTOMATION
    assert normalize_plan("store+automation") == Plan.STORE_AUTOMATION
    assert normalize_plan("store_automation_crm") == Plan.STORE_AUTOMATION_CRM
    assert normalize_plan("crm") == Plan.STORE_AUTOMATION_CRM
    assert normalize_plan("premium") == Plan.STORE_AUTOMATION_CRM
    assert normalize_plan("unknown_plan") == Plan.STORE


@pytest.mark.asyncio
async def test_get_tenant_plan_fallback():
    # Without DB or tenant not found, falls back to STORE
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    plan = await get_tenant_plan(uuid4(), mock_session)
    assert plan == Plan.STORE

    # With exception also fallback
    mock_session2 = AsyncMock()
    mock_session2.execute = AsyncMock(side_effect=Exception("db error"))
    plan2 = await get_tenant_plan(uuid4(), mock_session2)
    assert plan2 == Plan.STORE


@pytest.mark.asyncio
async def test_get_tenant_plan_with_mock_tenant():
    mock_session = AsyncMock()
    mock_tenant = MagicMock()
    mock_tenant.plan = "store_automation"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute = AsyncMock(return_value=mock_result)

    # The function tries to read Tenant.id and uses select; we mock tenant.plan attribute access
    # Our mock_tenant.plan should be normalized
    # Note: get_tenant_plan checks getattr(tenant, "plan", None)
    # So we need to set plan attribute directly
    mock_tenant.plan = "store_automation"
    plan = await get_tenant_plan(uuid4(), mock_session)
    # Since we mocked Tenant lookup, it will return mocked tenant with plan "store_automation"
    assert plan == Plan.STORE_AUTOMATION

    # For CRM
    mock_tenant2 = MagicMock()
    mock_tenant2.plan = "crm"
    mock_result2 = MagicMock()
    mock_result2.scalar_one_or_none.return_value = mock_tenant2
    mock_session.execute = AsyncMock(return_value=mock_result2)
    plan2 = await get_tenant_plan(uuid4(), mock_session)
    assert plan2 == Plan.STORE_AUTOMATION_CRM


def test_require_feature_dependency_structure():
    from apps.api.core.feature_flags import require_feature
    dep = require_feature(Feature.INSTAGRAM_AUTOMATION)
    assert callable(dep)

    # The checker should be async and expect to raise if not allowed
    # We test via has_feature indirectly
    assert has_feature(Plan.STORE, Feature.INSTAGRAM_AUTOMATION) is False
    assert has_feature(Plan.STORE_AUTOMATION, Feature.INSTAGRAM_AUTOMATION) is True


@pytest.mark.asyncio
async def test_feature_flag_enforcement_via_api():
    """Simulate API enforcement: tenant with STORE cannot access automation routes."""
    from apps.api.core.feature_flags import require_feature
    from fastapi import HTTPException
    from unittest.mock import patch

    # Create dependency with feature that STORE doesn't have
    checker = require_feature(Feature.INSTAGRAM_AUTOMATION)

    class FakeUser:
        tenant_id = uuid4()
        id = uuid4()
    fake_user = FakeUser()
    fake_request = MagicMock()
    mock_session = AsyncMock()
    # Mock get_tenant_plan to return STORE
    with patch("apps.api.core.feature_flags.get_tenant_plan", new=AsyncMock(return_value=Plan.STORE)):
        with pytest.raises(HTTPException) as exc:
            await checker(request=fake_request, user=fake_user, session=mock_session)
        assert exc.value.status_code == 403
        assert "Upgrade required" in exc.value.detail

    # With CRM plan, should pass
    with patch("apps.api.core.feature_flags.get_tenant_plan", new=AsyncMock(return_value=Plan.STORE_AUTOMATION_CRM)):
        result = await checker(request=fake_request, user=fake_user, session=mock_session)
        assert result == Plan.STORE_AUTOMATION_CRM
