"""Feature flags and plan entitlements.

Implements the three plans from requirements.md section 2 via feature flags,
not separate applications.
"""

from __future__ import annotations

from enum import Enum
from typing import Set

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from infalette_database.models.user import User


class Plan(str, Enum):
    STORE = "store"
    STORE_AUTOMATION = "store_automation"
    STORE_AUTOMATION_CRM = "store_automation_crm"


class Feature(str, Enum):
    CUSTOM_STOREFRONT = "custom_storefront"
    PRODUCTS = "products"
    CART_CHECKOUT = "cart_checkout"
    ORDERS = "orders"
    SEO = "seo"
    INSTAGRAM_AUTOMATION = "instagram_automation"
    WHATSAPP_AUTOMATION = "whatsapp_automation"
    CHECKOUT_LINKS = "checkout_links"
    UNIFIED_INBOX = "unified_inbox"
    CUSTOMER_PROFILES = "customer_profiles"
    FUNNEL_ANALYTICS = "funnel_analytics"
    # Tier distinctions (spec §2): Limited vs Full funnel, Basic vs Advanced
    FUNNEL_FULL = "funnel_full"
    ADVANCED_DASHBOARD = "advanced_dashboard"
    ABANDONED_SEGMENTS = "abandoned_segments"
    SALES_DASHBOARD = "sales_dashboard"
    CSV_EXPORTS = "csv_exports"


PLAN_FEATURES: dict[Plan, Set[Feature]] = {
    Plan.STORE: {
        Feature.CUSTOM_STOREFRONT,
        Feature.PRODUCTS,
        Feature.CART_CHECKOUT,
        Feature.ORDERS,
        Feature.SEO,
        # sales dashboard basic only
        Feature.SALES_DASHBOARD,
    },
    Plan.STORE_AUTOMATION: {
        Feature.CUSTOM_STOREFRONT,
        Feature.PRODUCTS,
        Feature.CART_CHECKOUT,
        Feature.ORDERS,
        Feature.SEO,
        Feature.INSTAGRAM_AUTOMATION,
        Feature.WHATSAPP_AUTOMATION,
        Feature.CHECKOUT_LINKS,
        Feature.UNIFIED_INBOX,
        Feature.SALES_DASHBOARD,
        # funnel limited
        Feature.FUNNEL_ANALYTICS,
    },
    Plan.STORE_AUTOMATION_CRM: {
        # all features
        Feature.CUSTOM_STOREFRONT,
        Feature.PRODUCTS,
        Feature.CART_CHECKOUT,
        Feature.ORDERS,
        Feature.SEO,
        Feature.INSTAGRAM_AUTOMATION,
        Feature.WHATSAPP_AUTOMATION,
        Feature.CHECKOUT_LINKS,
        Feature.UNIFIED_INBOX,
        Feature.CUSTOMER_PROFILES,
        Feature.FUNNEL_ANALYTICS,
        Feature.FUNNEL_FULL,  # Full funnel (Store+Automation is Limited)
        Feature.ADVANCED_DASHBOARD,  # Advanced sales dashboard & attribution
        Feature.ABANDONED_SEGMENTS,
        Feature.SALES_DASHBOARD,
        Feature.CSV_EXPORTS,
    },
}

# Quotas per plan (None = unlimited)
PLAN_QUOTAS: dict[Plan, dict[str, int | None]] = {
    Plan.STORE: {"products": 100, "orders_per_month": 500, "messages_per_month": 0, "automations": 0},
    Plan.STORE_AUTOMATION: {"products": 500, "orders_per_month": 2000, "messages_per_month": 5000, "automations": 10},
    Plan.STORE_AUTOMATION_CRM: {"products": None, "orders_per_month": None, "messages_per_month": 20000, "automations": None},
}


def normalize_plan(plan_str: str) -> Plan:
    p = plan_str.lower().strip()
    if p in ("store", "store_plan", "basic"):
        return Plan.STORE
    if p in ("store_automation", "store+automation", "store_automation_plan"):
        return Plan.STORE_AUTOMATION
    if p in ("store_automation_crm", "store+automation+crm", "crm", "premium"):
        return Plan.STORE_AUTOMATION_CRM
    # fallback: treat unknown as store
    return Plan.STORE


async def get_tenant_plan(tenant_id, session: AsyncSession) -> Plan:
    """Resolve tenant plan from DB. Falls back to STORE if not found."""
    try:
        from infalette_database.models.tenant import Tenant
        from uuid import UUID

        tid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
        result = await session.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if tenant and getattr(tenant, "plan", None):
            return normalize_plan(tenant.plan)
    except Exception:
        pass
    return Plan.STORE


def has_feature(plan: Plan, feature: Feature) -> bool:
    return feature in PLAN_FEATURES.get(plan, set())


def require_feature(feature: Feature):
    """Dependency that enforces feature flag based on current user's tenant plan."""

    async def checker(
        request: Request,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
    ):
        plan = await get_tenant_plan(user.tenant_id, session)
        if not has_feature(plan, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature.value}' not available on plan '{plan.value}'. Upgrade required.",
            )
        # also stash plan on request for downstream use
        request.state.tenant_plan = plan
        return plan

    return checker


def get_plan_quota(plan: Plan, key: str) -> int | None:
    return PLAN_QUOTAS.get(plan, {}).get(key)


# ---------------------------------------------------------------- quotas
def _count_usage(tenant_id, session: AsyncSession, quota_key: str):
    """Return a coroutine computing current usage for a quota key."""
    from sqlalchemy import func

    if quota_key == "products":
        from infalette_database.models.product import Product

        async def _count():
            res = await session.execute(
                select(func.count(Product.id)).where(Product.tenant_id == tenant_id)
            )
            return int(res.scalar() or 0)

        return _count

    if quota_key == "automations":
        from infalette_database.models.automation_rule import AutomationRule

        async def _count():
            res = await session.execute(
                select(func.count(AutomationRule.id)).where(
                    AutomationRule.tenant_id == tenant_id
                )
            )
            return int(res.scalar() or 0)

        return _count

    if quota_key == "messages_per_month":
        from datetime import datetime, timezone

        from infalette_database.models.conversation import Conversation
        from infalette_database.models.message import Message

        async def _count():
            month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            res = await session.execute(
                select(func.count(Message.id))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(
                    Conversation.tenant_id == tenant_id,
                    Message.created_at >= month_start,
                )
            )
            return int(res.scalar() or 0)

        return _count

    # orders_per_month
    from infalette_database.models.order import Order

    async def _count():
        from datetime import datetime, timezone

        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        res = await session.execute(
            select(func.count(Order.id)).where(
                Order.tenant_id == tenant_id,
                Order.created_at >= month_start,
            )
        )
        return int(res.scalar() or 0)

    return _count


async def check_quota(tenant_id, session: AsyncSession, quota_key: str) -> dict:
    """Evaluate plan quota for a resource.

    Returns {"allowed": bool, "used": int, "limit": int|None, "plan": Plan}.
    limit None => unlimited. Never raises for unknown keys.
    """
    plan = await get_tenant_plan(tenant_id, session)
    limit = get_plan_quota(plan, quota_key)
    if limit is None:
        return {"allowed": True, "used": 0, "limit": None, "plan": plan}
    counter = _count_usage(tenant_id, session, quota_key)
    try:
        used = await counter()
    except Exception:
        # Fail open on counting errors — availability over strictness
        return {"allowed": True, "used": -1, "limit": limit, "plan": plan}
    return {
        "allowed": used < limit,
        "used": used,
        "limit": limit,
        "plan": plan,
    }


def enforce_quota(quota_key: str):
    """Dependency factory: reject writes once the plan quota is exhausted."""

    async def checker(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
    ):
        result = await check_quota(user.tenant_id, session, quota_key)
        if not result["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Plan '{result['plan'].value}' limit reached: {quota_key} "
                    f"({result['used']}/{result['limit']}). Upgrade required."
                ),
            )
        return result

    return checker
