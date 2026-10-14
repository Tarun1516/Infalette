"""Scheduled report services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.report_schedule import ReportSchedule

VALID_REPORT_TYPES = {"orders", "customers", "leads"}
VALID_FREQUENCIES = {"daily", "weekly"}


async def generate_report_csv(
    tenant_id: UUID, report_type: str, session: AsyncSession
) -> tuple[str | None, str]:
    """Build an on-demand tenant-scoped CSV export.

    Returns (csv_text, filename); csv_text is None for unknown types.
    """
    import csv
    import io
    from datetime import datetime as _dt

    if report_type not in VALID_REPORT_TYPES:
        return None, f"{report_type}.csv"

    rows: list[list] = []
    header: list[str] = []

    if report_type == "orders":
        from infalette_database.models.order import Order

        result = await session.execute(
            select(Order)
            .where(Order.tenant_id == tenant_id)
            .order_by(Order.created_at.desc())
            .limit(10000)
        )
        header = ["id", "status", "total_cents", "currency", "customer_id", "created_at"]
        for o in result.scalars():
            rows.append([
                str(o.id),
                getattr(o.status, "value", o.status),
                o.total_cents,
                o.currency,
                str(o.customer_id) if o.customer_id else "",
                o.created_at.isoformat() if o.created_at else "",
            ])
    elif report_type == "customers":
        from infalette_database.models.customer import Customer

        result = await session.execute(
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .order_by(Customer.created_at.desc())
            .limit(10000)
        )
        header = ["id", "email", "first_name", "last_name", "phone", "created_at"]
        for c in result.scalars():
            rows.append([
                str(c.id), c.email or "", c.first_name or "", c.last_name or "",
                c.phone or "", c.created_at.isoformat() if c.created_at else "",
            ])
    elif report_type == "leads":
        from infalette_database.models.lead import Lead

        result = await session.execute(
            select(Lead)
            .where(Lead.tenant_id == tenant_id)
            .order_by(Lead.created_at.desc())
            .limit(10000)
        )
        header = ["id", "email", "first_name", "last_name", "stage", "source", "created_at"]
        for l in result.scalars():
            rows.append([
                str(l.id), l.email or "", l.first_name or "", l.last_name or "",
                str(getattr(l.stage, "value", l.stage) or ""),
                l.source or "", l.created_at.isoformat() if l.created_at else "",
            ])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    filename = (
        f"{report_type}_{_dt.utcnow().strftime('%Y%m%d')}_{str(tenant_id)[:8]}.csv"
    )
    return buf.getvalue(), filename


async def list_schedules(tenant_id: UUID, session: AsyncSession) -> list[ReportSchedule]:
    result = await session.execute(
        select(ReportSchedule).where(ReportSchedule.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def get_schedule(
    tenant_id: UUID, schedule_id: UUID, session: AsyncSession
) -> ReportSchedule | None:
    result = await session.execute(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_schedule(
    tenant_id: UUID, data: dict, session: AsyncSession
) -> ReportSchedule | str:
    report_type = (data.get("report_type") or "").lower().strip()
    frequency = (data.get("frequency") or "daily").lower().strip()
    recipients = data.get("recipients") or []

    if report_type not in VALID_REPORT_TYPES:
        return f"report_type must be one of {sorted(VALID_REPORT_TYPES)}"
    if frequency not in VALID_FREQUENCIES:
        return f"frequency must be one of {sorted(VALID_FREQUENCIES)}"
    if not isinstance(recipients, list) or not recipients:
        return "recipients must be a non-empty list of email addresses"

    schedule = ReportSchedule(
        tenant_id=tenant_id,
        name=data.get("name") or f"{report_type}-{frequency}",
        report_type=report_type,
        frequency=frequency,
        recipients_json=[str(r) for r in recipients],
        is_active=bool(data.get("is_active", True)),
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return schedule


async def update_schedule(
    tenant_id: UUID, schedule_id: UUID, data: dict, session: AsyncSession
) -> ReportSchedule | None:
    schedule = await get_schedule(tenant_id, schedule_id, session)
    if not schedule:
        return None
    for key in ("name", "report_type", "frequency", "is_active"):
        if key in data and data[key] is not None:
            setattr(schedule, key, data[key])
    if "recipients" in data and isinstance(data["recipients"], list):
        schedule.recipients_json = [str(r) for r in data["recipients"]]
    await session.commit()
    await session.refresh(schedule)
    return schedule


async def delete_schedule(
    tenant_id: UUID, schedule_id: UUID, session: AsyncSession
) -> bool:
    result = await session.execute(
        sa_delete(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == tenant_id,
        )
    )
    await session.commit()
    return (result.rowcount or 0) > 0
