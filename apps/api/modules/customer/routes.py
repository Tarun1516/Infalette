"""Customer management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import Feature, require_feature

router = APIRouter()


@router.get("/")
async def list_customers(
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List customers for the tenant."""
    from apps.api.modules.customer.services import list_customers
    return await list_customers(user.tenant_id, session, search, status)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new customer."""
    from apps.api.modules.customer.services import create_customer
    return await create_customer(user.tenant_id, data, session)


@router.get("/{customer_id}")
async def get_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a customer by ID."""
    from apps.api.modules.customer.services import get_customer
    customer = await get_customer(user.tenant_id, customer_id, session)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a customer."""
    from apps.api.modules.customer.services import update_customer
    return await update_customer(user.tenant_id, customer_id, data, session)


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a customer."""
    from apps.api.modules.customer.services import delete_customer
    await delete_customer(user.tenant_id, customer_id, session)
    return {"message": "Customer deleted"}


@router.get("/{customer_id}/orders")
async def get_customer_orders(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get all orders for a customer."""
    from apps.api.modules.customer.services import get_customer_orders
    return await get_customer_orders(user.tenant_id, customer_id, session)


@router.get("/stats/overview", dependencies=[Depends(require_feature(Feature.CUSTOMER_PROFILES))])
async def get_customers_overview_stats(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Aggregate customer stats for the admin customers page.

    Registered before the ``/{customer_id}`` route so ``stats`` is never
    captured as a customer id.
    """
    from sqlalchemy import func as _func

    from infalette_database.models.customer import Customer
    from infalette_database.models.order import Order

    total_customers = (
        await session.execute(
            _select(_func.count(Customer.id)).where(Customer.tenant_id == user.tenant_id)
        )
    ).scalar() or 0

    customers_with_orders = (
        await session.execute(
            _select(_func.count(_func.distinct(Order.customer_id))).where(
                Order.tenant_id == user.tenant_id
            )
        )
    ).scalar() or 0

    lifetime_value = (
        await session.execute(
            _select(_func.coalesce(_func.sum(Order.total_cents), 0)).where(
                Order.tenant_id == user.tenant_id
            )
        )
    ).scalar() or 0

    return {
        "total_customers": int(total_customers),
        "customers_with_orders": int(customers_with_orders),
        "lifetime_value_cents": int(lifetime_value),
        "average_lifetime_value_cents": int(lifetime_value // total_customers)
        if total_customers
        else 0,
    }


@router.get("/{customer_id}/stats", dependencies=[Depends(require_feature(Feature.CUSTOMER_PROFILES))])
async def get_customer_stats(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get customer statistics."""
    from apps.api.modules.customer.services import get_customer_stats
    return await get_customer_stats(user.tenant_id, customer_id, session)


@router.get("/{customer_id}/timeline", dependencies=[Depends(require_feature(Feature.CUSTOMER_PROFILES))])
async def get_customer_timeline(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get CRM timeline for a customer – events filtered by customer_id."""
    from apps.api.modules.customer.services import get_customer, get_customer_timeline
    customer = await get_customer(user.tenant_id, customer_id, session)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    events = await get_customer_timeline(user.tenant_id, customer_id, session)
    return [
        {
            "id": str(e.id),
            "tenant_id": str(e.tenant_id),
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "event_type": getattr(e, "event_type", getattr(e, "type", None)),
            "payload": e.payload_json,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.post("/{customer_id}/consent/withdraw")
async def withdraw_consent_alias(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """DPDP withdrawal alias — revokes all marketing consent flags."""
    from apps.api.modules.customer.services import update_customer_consent

    customer = await update_customer_consent(
        user.tenant_id,
        customer_id,
        {"marketing_email": False, "marketing_whatsapp": False, "marketing_sms": False, "withdrawn_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
        session,
    )
    return {"id": str(customer.id), "consent_json": customer.consent_json, "status": "withdrawn"}


@router.patch("/{customer_id}/consent")
async def update_consent(
    customer_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update marketing consent flags (DPDP). Body: {"consent": {...}}."""
    consent = data.get("consent") or {}
    if not isinstance(consent, dict) or not consent:
        raise HTTPException(status_code=422, detail="consent object required")
    from apps.api.modules.customer.services import update_customer_consent
    customer = await update_customer_consent(user.tenant_id, customer_id, consent, session)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "id": str(customer.id),
        "consent_json": customer.consent_json,
    }


@router.get("/{customer_id}/export")
async def export_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Export all personal data held for this customer (DPDP portability)."""
    from apps.api.modules.customer.services import export_customer_data
    data = await export_customer_data(user.tenant_id, customer_id, session)
    if data is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return data


@router.post("/{customer_id}/erase")
async def erase_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Anonymize this customer's personal data (DPDP right to erasure)."""
    from apps.api.modules.customer.services import erase_customer_data
    result = await erase_customer_data(user.tenant_id, customer_id, session)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result
