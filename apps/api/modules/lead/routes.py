"""Lead management routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user

router = APIRouter()


@router.get("/")
async def list_leads(
    status: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List leads for the tenant."""
    from apps.api.modules.lead.services import list_leads
    return await list_leads(user.tenant_id, session, status, source)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Create a new lead."""
    from apps.api.modules.lead.services import create_lead
    return await create_lead(user.tenant_id, data, session)


@router.get("/{lead_id}")
async def get_lead(
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get a lead by ID."""
    from apps.api.modules.lead.services import get_lead
    lead = await get_lead(user.tenant_id, lead_id, session)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}")
async def update_lead(
    lead_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update a lead."""
    from apps.api.modules.lead.services import update_lead
    return await update_lead(user.tenant_id, lead_id, data, session)


@router.patch("/{lead_id}/stage")
async def update_lead_stage(
    lead_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Update only a lead's stage (admin leads page stage dropdown)."""
    from apps.api.modules.lead.services import update_lead

    stage = (data or {}).get("stage") or (data or {}).get("status")
    if not stage:
        raise HTTPException(status_code=422, detail="stage required")
    return await update_lead(user.tenant_id, lead_id, {"status": stage}, session)


class LeadImportRow(BaseModel):
    """One CSV/JSON lead row; unknown keys ignored."""

    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = "import"
    status: Optional[str] = "new"

    model_config = {"extra": "ignore"}


def _parse_csv(text: str) -> list[dict]:
    """Parse uploaded CSV text into lead dicts."""
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(text)))
    return [{k.strip().lower(): (v or "").strip() for k, v in row.items()} for row in rows]


async def _import_rows(tenant_id: UUID, rows: list[dict], session):
    from apps.api.modules.lead.services import bulk_import_leads

    cleaned = []
    for r in rows:
        parsed = LeadImportRow(**{k: v for k, v in r.items() if v})
        cleaned.append(parsed.model_dump(exclude_none=True))
    return await bulk_import_leads(tenant_id, cleaned, session)


@router.post("/import")
async def import_leads_multipart(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """CSV upload import (multipart/form-data) from the admin leads page."""
    raw = await file.read()
    text = raw.decode("utf-8-sig", errors="replace")
    rows = _parse_csv(text)
    if not rows:
        raise HTTPException(status_code=422, detail="No rows found in CSV")
    return await _import_rows(user.tenant_id, rows, session)


@router.post("/bulk-import")
async def bulk_import_leads_json(
    leads: list[dict],
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Bulk import leads (JSON array)."""
    return await _import_rows(user.tenant_id, leads, session)


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Delete a lead."""
    from apps.api.modules.lead.services import delete_lead
    await delete_lead(user.tenant_id, lead_id, session)
    return {"message": "Lead deleted"}


@router.post("/{lead_id}/convert")
async def convert_lead(
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Convert a lead to a customer."""
    from apps.api.modules.lead.services import convert_lead
    return await convert_lead(user.tenant_id, lead_id, session)


@router.get("/{lead_id}/timeline")
async def get_lead_timeline(
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Get CRM timeline for a lead – events filtered by lead_id."""
    from apps.api.modules.lead.services import get_lead_timeline, get_lead
    lead = await get_lead(user.tenant_id, lead_id, session)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    events = await get_lead_timeline(user.tenant_id, lead_id, session)
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


@router.post("/bulk-import")
async def bulk_import_leads_json_legacy(
    leads: list[dict],
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Legacy alias — JSON bulk import."""
    return await _import_rows(user.tenant_id, leads, session)
