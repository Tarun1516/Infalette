"""Scheduled report management routes (CRM plan — CSV exports entitlement)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.session import get_async_session
from infalette_auth.dependencies import get_current_user
from apps.api.core.feature_flags import Feature, require_feature

router = APIRouter(dependencies=[Depends(require_feature(Feature.CSV_EXPORTS))])


@router.get("/")
async def list_report_schedules(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """List scheduled reports for the tenant."""
    from apps.api.modules.reports.services import list_schedules
    return await list_schedules(user.tenant_id, session)


@router.post("/", status_code=201)
async def create_report_schedule(
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """Schedule a recurring report. Body: {report_type, frequency, recipients, name}."""
    from apps.api.modules.reports.services import create_schedule
    schedule = await create_schedule(user.tenant_id, data, session)
    if isinstance(schedule, str):
        raise HTTPException(status_code=422, detail=schedule)
    return _serialize(schedule)


@router.get("/{schedule_id}")
async def get_report_schedule(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.reports.services import get_schedule
    schedule = await get_schedule(user.tenant_id, schedule_id, session)
    if not schedule:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return _serialize(schedule)


@router.patch("/{schedule_id}")
async def update_report_schedule(
    schedule_id: UUID,
    data: dict,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.reports.services import update_schedule
    schedule = await update_schedule(user.tenant_id, schedule_id, data, session)
    if not schedule:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return _serialize(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_report_schedule(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    from apps.api.modules.reports.services import delete_schedule
    deleted = await delete_schedule(user.tenant_id, schedule_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report schedule not found")


def _serialize(s) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "report_type": s.report_type,
        "frequency": s.frequency,
        "recipients": s.recipients_json,
        "is_active": s.is_active,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "run_count": s.run_count,
    }


@router.get("/export/{report_type}")
async def export_report_csv(
    report_type: str,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    """On-demand CSV export (orders | customers | leads) for the tenant."""
    from fastapi.responses import Response

    from apps.api.modules.reports.services import generate_report_csv

    csv_text, filename = await generate_report_csv(
        user.tenant_id, report_type.lower().strip(), session
    )
    if csv_text is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported report type '{report_type}' (use: orders, customers, leads)",
        )
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
