"""Lead management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.lead import Lead, LeadStage
from infalette_database.models.event import Event
from infalette_analytics.event_bus import record_event


async def list_leads(
    tenant_id: UUID,
    session: AsyncSession,
    status: Optional[str] = None,
    source: Optional[str] = None,
) -> list[Lead]:
    """List leads for a tenant."""
    query = select(Lead).where(Lead.tenant_id == tenant_id)
    if status:
        # Normalize status to string value whether LeadStage or plain string
        try:
            val = LeadStage(status).value if isinstance(status, str) else status
        except ValueError:
            val = status
        query = query.where(Lead._status == val)  # type: ignore[attr-defined]
        # Fallback to hybrid property if _status not available (older model)
        # query = query.where(Lead.status == status)
    if source:
        query = query.where(Lead.source == source)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_lead(tenant_id: UUID, lead_id: UUID, session: AsyncSession) -> Lead | None:
    """Get a lead by ID."""
    result = await session.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_lead(tenant_id: UUID, data: dict, session: AsyncSession) -> Lead:
    """Create a new lead."""
    # Normalize stage/status inputs – accept both `stage` and `status` keys
    raw_stage = data.get("stage") or data.get("status") or "new"
    if isinstance(raw_stage, str):
        try:
            # try to map to LeadStage enum value
            stage_val = LeadStage(raw_stage).value
        except ValueError:
            stage_val = raw_stage
    else:
        stage_val = raw_stage
    lead = Lead(
        tenant_id=tenant_id,
        email=data.get("email"),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        phone=data.get("phone"),
        source=data.get("source", "website"),
        status=stage_val,
        score=data.get("score", 0),
        tags=data.get("tags", []),
        metadata_json=data.get("metadata", {}),
        # Attribution & ownership links
        campaign_id=data.get("campaign_id"),
        customer_id=data.get("customer_id"),
        assigned_to=data.get("assigned_to"),
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    # Record event
    await record_event(
        tenant_id=tenant_id,
        actor_id=None,
        event_type="lead.created",
        payload={"lead_id": str(lead.id), "source": lead.source},
        session=session,
    )

    return lead


async def update_lead(
    tenant_id: UUID,
    lead_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Lead | None:
    """Update a lead."""
    lead = await get_lead(tenant_id, lead_id, session)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    old_status = lead.status
    # Handle stage/status synonym
    if "stage" in data and "status" not in data:
        data["status"] = data.pop("stage")
    for key, value in data.items():
        if hasattr(lead, key) and value is not None:
            # Coerce LeadStage enum if applicable
            if key in ("status", "stage") and isinstance(value, str):
                try:
                    value = LeadStage(value).value
                except ValueError:
                    pass
            setattr(lead, key, value)

    if old_status != lead.status:
        # Use canonical stage string for event type
        stage_str = lead.status if isinstance(lead.status, str) else lead.status.value  # type: ignore
        await record_event(
            tenant_id=tenant_id,
            actor_id=None,
            event_type=f"lead.{stage_str}",
            payload={"lead_id": str(lead_id), "old_status": str(old_status), "new_status": str(stage_str)},
            session=session,
        )
        # Also emit generic stage_changed
        await record_event(
            tenant_id=tenant_id,
            actor_id=None,
            event_type="lead.stage_changed",
            payload={"lead_id": str(lead_id), "from": str(old_status), "to": str(stage_str)},
            session=session,
        )

    await session.commit()
    await session.refresh(lead)
    return lead


async def delete_lead(tenant_id: UUID, lead_id: UUID, session: AsyncSession) -> None:
    """Delete a lead."""
    await session.execute(
        delete(Lead).where(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
        )
    )
    await session.commit()


async def convert_lead(
    tenant_id: UUID,
    lead_id: UUID,
    session: AsyncSession,
) -> dict:
    """Convert a lead to a customer."""
    lead = await get_lead(tenant_id, lead_id, session)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from infalette_database.models.customer import Customer
    customer = Customer(
        tenant_id=tenant_id,
        email=lead.email,
        first_name=lead.first_name,
        last_name=lead.last_name,
        phone=lead.phone,
        status="active",
        tags=lead.tags,
        metadata_json=lead.metadata_json,
    )
    session.add(customer)

    await session.execute(
        update(Lead)
        .where(Lead.id == lead_id)
        .values(status="converted")
        .execution_options(synchronize_session="fetch")
    )

    await record_event(
        tenant_id=tenant_id,
        actor_id=None,
        event_type="lead.converted",
        payload={"lead_id": str(lead_id), "customer_id": str(customer.id)},
        session=session,
    )

    await session.commit()
    await session.refresh(customer)

    return {"customer_id": str(customer.id), "lead_id": str(lead_id)}


async def bulk_import_leads(
    tenant_id: UUID,
    leads_data: list[dict],
    session: AsyncSession,
) -> dict:
    """Bulk import leads."""
    imported = 0
    for data in leads_data:
        raw = data.get("status") or data.get("stage") or "new"
        try:
            stage_val = LeadStage(raw).value if isinstance(raw, str) else raw
        except ValueError:
            stage_val = raw
        lead = Lead(
            tenant_id=tenant_id,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            phone=data.get("phone"),
            source=data.get("source", "import"),
            status=stage_val,
            score=data.get("score", 0),
            tags=data.get("tags", []),
            metadata_json=data.get("metadata", {}),
            campaign_id=data.get("campaign_id"),
            customer_id=data.get("customer_id"),
            assigned_to=data.get("assigned_to"),
        )
        session.add(lead)
        imported += 1

    await session.commit()

    await record_event(
        tenant_id=tenant_id,
        actor_id=None,
        event_type="lead.bulk_import",
        payload={"count": imported},
        session=session,
    )

    return {"imported": imported}


async def get_lead_timeline(
    tenant_id: UUID,
    lead_id: UUID,
    session: AsyncSession,
    limit: int = 100,
) -> list[Event]:
    """Get CRM timeline for a lead – events where payload contains lead_id or actor_id matches."""
    lead_id_str = str(lead_id)
    # Query events for tenant, filter in Python for JSON containment to stay DB-agnostic
    # plus also actor_id match
    result = await session.execute(
        select(Event)
        .where(Event.tenant_id == tenant_id)
        .order_by(Event.created_at.desc())
        .limit(limit * 2)  # fetch extra to allow post-filter
    )
    events = list(result.scalars().all())
    filtered: list[Event] = []
    for ev in events:
        payload = ev.payload_json or {}
        # Check various id locations
        if ev.actor_id == lead_id:
            filtered.append(ev)
        elif payload.get("lead_id") == lead_id_str:
            filtered.append(ev)
        elif payload.get("customer_id") == lead_id_str:
            filtered.append(ev)
        elif isinstance(payload, dict) and lead_id_str in {str(v) for v in payload.values() if isinstance(v, str)}:
            filtered.append(ev)
        # Also check if payload is nested string compare (fallback)
        if len(filtered) >= limit:
            break
    # More precise DB-level filter as alternative (if using Postgres JSONB)
    # Could also do: Event.payload_json["lead_id"].astext == lead_id_str
    # We already have Python filtering, but attempt also DB filter for efficiency if needed
    if not filtered:
        try:
            result = await session.execute(
                select(Event).where(
                    Event.tenant_id == tenant_id,
                    or_(
                        Event.actor_id == lead_id,
                        Event.payload_json["lead_id"].astext == lead_id_str,
                        Event.payload_json["customer_id"].astext == lead_id_str,
                    ),
                ).order_by(Event.created_at.desc()).limit(limit)
            )
            filtered = list(result.scalars().all())
        except Exception:
            pass
    return filtered[:limit]
