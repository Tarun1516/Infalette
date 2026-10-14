"""Customer management services."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.customer import Customer
from infalette_database.models.order import Order
from infalette_database.models.event import Event


async def list_customers(
    tenant_id: UUID,
    session: AsyncSession,
    search: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Customer]:
    """List customers for a tenant."""
    query = select(Customer).where(Customer.tenant_id == tenant_id)
    if search:
        query = query.where(
            (Customer.email.ilike(f"%{search}%"))
            | (Customer.first_name.ilike(f"%{search}%"))
            | (Customer.last_name.ilike(f"%{search}%"))
        )
    if status:
        query = query.where(Customer.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_customer(tenant_id: UUID, customer_id: UUID, session: AsyncSession) -> Customer | None:
    """Get a customer by ID."""
    result = await session.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_customer(tenant_id: UUID, data: dict, session: AsyncSession) -> Customer:
    """Create a new customer."""
    customer = Customer(
        tenant_id=tenant_id,
        email=data.get("email"),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        phone=data.get("phone"),
        status=data.get("status", "active"),
        tags=data.get("tags", []),
        metadata_json=data.get("metadata", {}),
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


async def update_customer(
    tenant_id: UUID,
    customer_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Customer | None:
    """Update a customer."""
    customer = await get_customer(tenant_id, customer_id, session)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    for key, value in data.items():
        if hasattr(customer, key) and value is not None:
            setattr(customer, key, value)

    await session.commit()
    await session.refresh(customer)
    return customer


async def delete_customer(tenant_id: UUID, customer_id: UUID, session: AsyncSession) -> None:
    """Delete a customer."""
    await session.execute(
        delete(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def get_customer_orders(
    tenant_id: UUID,
    customer_id: UUID,
    session: AsyncSession,
) -> list[Order]:
    """Get all orders for a customer."""
    result = await session.execute(
        select(Order).where(
            Order.customer_id == customer_id,
            Order.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())


async def get_customer_stats(
    tenant_id: UUID,
    customer_id: UUID,
    session: AsyncSession,
) -> dict:
    """Get customer statistics."""
    orders = await get_customer_orders(tenant_id, customer_id, session)
    total_orders = len(orders)
    total_spent = sum(o.total_cents for o in orders)
    return {
        "total_orders": total_orders,
        "total_spent_cents": total_spent,
        "average_order_value": total_spent // total_orders if total_orders > 0 else 0,
    }


async def get_customer_timeline(
    tenant_id: UUID,
    customer_id: UUID,
    session: AsyncSession,
    limit: int = 100,
) -> list[Event]:
    """Get CRM timeline for a customer – events where payload contains customer_id or actor_id."""
    cid_str = str(customer_id)
    result = await session.execute(
        select(Event)
        .where(Event.tenant_id == tenant_id)
        .order_by(Event.created_at.desc())
        .limit(limit * 2)
    )
    events = list(result.scalars().all())
    filtered: list[Event] = []
    for ev in events:
        payload = ev.payload_json or {}
        if ev.actor_id == customer_id:
            filtered.append(ev)
        elif payload.get("customer_id") == cid_str:
            filtered.append(ev)
        elif payload.get("lead_id") == cid_str:
            filtered.append(ev)
        elif isinstance(payload, dict) and cid_str in {str(v) for v in payload.values() if isinstance(v, str)}:
            filtered.append(ev)
        if len(filtered) >= limit:
            break
    if not filtered:
        try:
            result = await session.execute(
                select(Event).where(
                    Event.tenant_id == tenant_id,
                    or_(
                        Event.actor_id == customer_id,
                        Event.payload_json["customer_id"].astext == cid_str,
                        Event.payload_json["lead_id"].astext == cid_str,
                    ),
                ).order_by(Event.created_at.desc()).limit(limit)
            )
            filtered = list(result.scalars().all())
        except Exception:
            pass
    return filtered[:limit]


async def update_customer_consent(
    tenant_id: UUID,
    customer_id: UUID,
    consent: dict,
    session: AsyncSession,
) -> Customer:
    """Update a customer's marketing consent flags (DPDP §9).

    Records the mandatory customer.consent_changed event.
    """
    from infalette_analytics.event_bus import record_event

    customer = await get_customer(tenant_id, customer_id, session)
    if not customer:
        return None

    current = dict(customer.consent_json or {})
    current.update(consent)
    current["updated_at"] = datetime.utcnow().isoformat()
    customer.consent_json = current
    await session.commit()
    await session.refresh(customer)

    try:
        await record_event(
            tenant_id=tenant_id,
            actor_id=customer_id,
            event_type="customer.consent_changed",
            payload={"customer_id": str(customer_id), "consent": consent},
            session=session,
        )
    except Exception:
        pass
    return customer


async def export_customer_data(
    tenant_id: UUID,
    customer_id: UUID,
    session: AsyncSession,
) -> dict:
    """Export all personal data held for a customer (DPDP data portability)."""
    from sqlalchemy import select
    from infalette_database.models.order import Order
    from infalette_database.models.conversation import Conversation
    from infalette_database.models.message import Message
    from infalette_database.models.lead import Lead
    from infalette_database.models.social_identity import SocialIdentity
    from infalette_database.models.event import Event

    customer = await get_customer(tenant_id, customer_id, session)
    if not customer:
        return None

    def _dump(obj) -> dict:
        return {c: getattr(obj, c) for c in obj.__table__.columns.keys()}

    orders = list(
        (await session.execute(select(Order).where(Order.customer_id == customer_id))).scalars()
    )
    # DPDP data-portability must cover ONLY this customer's records — never
    # other customers' conversations or events.
    conversations = list(
        (
            await session.execute(
                select(Conversation).where(
                    Conversation.tenant_id == tenant_id,
                    Conversation.customer_id == customer_id,
                )
            )
        ).scalars()
    )
    conv_ids = {c.id for c in conversations}
    messages = []
    if conv_ids:
        rows = await session.execute(
            select(Message).where(Message.conversation_id.in_(conv_ids))
        )
        messages = list(rows.scalars())
    leads = list(
        (await session.execute(select(Lead).where(Lead.customer_id == customer_id))).scalars()
    )
    identities = list(
        (
            await session.execute(
                select(SocialIdentity).where(SocialIdentity.customer_id == customer_id)
            )
        ).scalars()
    )
    all_events = list(
        (
            await session.execute(
                select(Event).where(Event.tenant_id == tenant_id).limit(2000)
            )
        ).scalars()
    )
    cust_key = str(customer_id)
    events = [
        e
        for e in all_events
        if str(getattr(e, "actor_id", None) or "") == cust_key
        or ((getattr(e, "payload_json", None) or {}).get("customer_id") == cust_key)
    ]

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "customer": {
            "id": str(customer.id),
            "email": customer.email,
            "phone": customer.phone,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "tags": customer.tags,
            "metadata_json": customer.metadata_json,
            "addresses_json": customer.addresses_json,
            "consent_json": customer.consent_json,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
        },
        "orders": [_dump(o) for o in orders],
        "leads": [_dump(l) for l in leads],
        "social_identities": [
            {"provider": i.provider, "provider_user_id": i.provider_user_id} for i in identities
        ],
        "conversations": [_dump(c) for c in conversations],
        "messages": [_dump(m) for m in messages],
        "events": [_dump(e) for e in events],
    }


async def erase_customer_data(
    tenant_id: UUID,
    customer_id: UUID,
    session: AsyncSession,
) -> dict:
    """Erase/anonymize a customer's personal data (DPDP right to erasure).

    Orders are retained (financial/legal requirement) but PII is stripped.
    """
    import uuid as _uuid

    from infalette_analytics.event_bus import record_event

    customer = await get_customer(tenant_id, customer_id, session)
    if not customer:
        return None

    anon_email = f"erased-{_uuid.uuid4().hex[:12]}@deleted.invalid"
    customer.email = anon_email
    customer.phone = None
    customer.first_name = "Erased"
    customer.last_name = "User"
    customer.addresses_json = []
    customer.metadata_json = {}
    tags = ["erased"]
    customer.tags = tags
    await session.commit()

    try:
        await record_event(
            tenant_id=tenant_id,
            actor_id=None,
            event_type="customer.erased",
            payload={"customer_id": str(customer_id)},
            session=session,
        )
    except Exception:
        pass

    return {
        "customer_id": str(customer_id),
        "status": "erased",
        "retained_email": anon_email,
    }
