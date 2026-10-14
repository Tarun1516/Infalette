"""Data export task — real CSV generation with S3 upload + email fallback."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime
from uuid import UUID

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.order import Order
from infalette_database.models.customer import Customer
from infalette_database.models.lead import Lead
from infalette_integrations.email.client import EmailClient

logger = logging.getLogger(__name__)


def _val(value):
    """Coerce enum/datetime/UUID values to CSV-safe primitives."""
    if value is None:
        return ""
    if hasattr(value, "value"):  # SAEnum members
        return value.value
    return str(value)


async def _build_csv_text(
    session: AsyncSession,
    tenant_id: UUID,
    export_type: str,
) -> tuple[str, int]:
    """Build CSV text for one export type, tenant-scoped.

    Returns:
        (csv_text, record_count)
    """
    if export_type == "orders":
        result = await session.execute(
            select(Order).where(Order.tenant_id == tenant_id)
        )
        rows = list(result.scalars().all())
        fieldnames = [
            "id", "status", "total_cents", "currency", "created_at", "customer_id",
        ]
        records = [
            {
                "id": str(o.id),
                "status": _val(o.status),
                "total_cents": o.total_cents,
                "currency": o.currency,
                "created_at": o.created_at.isoformat() if o.created_at else "",
                "customer_id": str(o.customer_id) if o.customer_id else "",
            }
            for o in rows
        ]
    elif export_type == "customers":
        result = await session.execute(
            select(Customer).where(Customer.tenant_id == tenant_id)
        )
        rows = list(result.scalars().all())
        fieldnames = ["id", "email", "first_name", "last_name", "status", "created_at"]
        records = [
            {
                "id": str(c.id),
                "email": c.email or "",
                "first_name": c.first_name or "",
                "last_name": c.last_name or "",
                "status": _val(c.status),
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in rows
        ]
    elif export_type == "leads":
        result = await session.execute(
            select(Lead).where(Lead.tenant_id == tenant_id)
        )
        rows = list(result.scalars().all())
        fieldnames = ["id", "email", "first_name", "last_name", "status", "source", "created_at"]
        records = [
            {
                "id": str(l.id),
                "email": l.email or "",
                "first_name": l.first_name or "",
                "last_name": l.last_name or "",
                "status": _val(l.status),
                "source": _val(l.source),
                "created_at": l.created_at.isoformat() if l.created_at else "",
            }
            for l in rows
        ]
    else:
        raise ValueError(f"Unsupported export_type: {export_type}")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue(), len(records)


async def export_tenant_data(
    session: AsyncSession,
    tenant_id: UUID,
    export_type: str,
    email: str = None,
) -> dict:
    """Export tenant data as CSV.

    Uploads to S3 under exports/{tenant_id}/{export_type}-{YYYYMMDD-HHMM}.csv.
    Falls back to emailing the CSV body when S3 is unavailable or the
    bucket is not configured.
    """
    csv_text, record_count = await _build_csv_text(session, tenant_id, export_type)

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
    key = f"exports/{tenant_id}/{export_type}-{timestamp}.csv"

    # Primary path: S3 upload
    try:
        from infalette_integrations.s3.client import S3Client

        s3 = S3Client()
        s3.upload_file(
            file_obj=csv_text.encode("utf-8"),
            key=key,
            content_type="text/csv",
        )
        return {
            "status": "completed",
            "storage": "s3",
            "key": key,
            "export_type": export_type,
            "records": record_count,
            "exported_at": datetime.utcnow().isoformat(),
            # Included so scheduled-report delivery can email the content.
            "csv_text": csv_text,
        }
    except Exception as exc:
        logger.warning(
            "S3 upload failed for %s (%s), falling back to email: %s",
            key,
            export_type,
            exc,
        )

    # Fallback path: email the CSV as a link-less body attachment
    if email:
        email_client = EmailClient()
        await email_client.send_email(
            to=email,
            subject=f"Data Export: {export_type}",
            html_content=(
                f"<p>Your {export_type} export is attached below.</p>"
                f"<pre>{csv_text}</pre>"
            ),
            text_content=csv_text,
            tenant_id=tenant_id,
        )
        return {
            "status": "completed",
            "storage": "email",
            "key": key,
            "export_type": export_type,
            "records": record_count,
            "exported_at": datetime.utcnow().isoformat(),
            "csv_text": csv_text,
        }

    return {
        "status": "failed",
        "storage": None,
        "key": key,
        "export_type": export_type,
        "records": record_count,
        "error": "S3 unavailable and no recipient email provided",
        "exported_at": datetime.utcnow().isoformat(),
    }


async def _run_daily_scheduled_reports() -> dict:
    """Run all due ReportSchedule rows (CRM CSV-exports entitlement).

    Falls back to exporting orders for CRM-plan tenants that have no
    explicit schedules, preserving the original behavior.
    """
    from infalette_database.session import get_session_factory
    from infalette_database.models.tenant import Tenant
    from infalette_database.models.plan import Plan
    from infalette_database.models.report_schedule import ReportSchedule

    factory = get_session_factory()
    results: dict[str, dict] = {}
    skipped = 0

    async with factory() as session:
        schedules = list(
            (
                await session.execute(
                    select(ReportSchedule).where(ReportSchedule.is_active.is_(True))
                )
            ).scalars()
        )
        schedule_ids = {s.tenant_id for s in schedules}

        # Fallback: CRM-plan tenants without explicit schedules keep daily orders export
        result = await session.execute(
            select(Tenant, Plan).join(Plan, Tenant.plan_id == Plan.id)
        )
        pairs = list(result.all())

    for tenant, plan in pairs:
        if tenant.id in schedule_ids:
            continue  # covered by explicit schedules below
        plan_label = " ".join(
            filter(None, [plan.slug or "", getattr(plan.plan_type, "value", "") or "", plan.name or ""])
        ).lower()
        if "crm" not in plan_label:
            skipped += 1
            continue
        try:
            async with factory() as session:
                outcome = await export_tenant_data(session, tenant.id, "orders")
            results[str(tenant.id)] = outcome
        except Exception as exc:
            logger.error(
                "Scheduled report failed for tenant %s: %s", tenant.id, exc, exc_info=True
            )

    # Explicit schedules — honor frequency (weekly runs only 7d after last)
    for schedule in schedules:
        try:
            if str(schedule.frequency).lower() == "weekly":
                last = schedule.last_run_at
                if last is not None and (datetime.utcnow() - last).days < 7:
                    results[f"{schedule.tenant_id}:{schedule.report_type}"] = {
                        "status": "skipped",
                        "reason": "weekly not due yet",
                    }
                    continue

            async with factory() as session:
                outcome = await export_tenant_data(
                    session, schedule.tenant_id, schedule.report_type
                )
                schedule.last_run_at = datetime.utcnow()
                schedule.run_count = (schedule.run_count or 0) + 1
                await session.commit()

            # Deliver the CSV content itself to configured recipients
            recipients = schedule.recipients_json or []
            csv_text = ""
            if isinstance(outcome, dict):
                csv_text = (
                    outcome.get("csv_text")
                    or outcome.get("content")
                    or ""
                )
            if recipients:
                from infalette_integrations.email.client import EmailClient

                preview = (
                    f"<p>Your scheduled '{schedule.report_type}' report is attached below.</p>"
                    + (
                        f"<pre>{str(csv_text)[:40000]}</pre>"
                        if csv_text
                        else f"<pre>Upload result: {str(outcome)[:2000]}</pre>"
                    )
                )
                for recipient in recipients:
                    await EmailClient().send_email(
                        to=recipient,
                        subject=f"Your {schedule.frequency} {schedule.report_type} report",
                        html_content=preview,
                        tenant_id=schedule.tenant_id,
                    )
            results[f"{schedule.tenant_id}:{schedule.report_type}"] = outcome
        except Exception as exc:
            logger.error(
                "Report schedule %s failed: %s", schedule.id, exc, exc_info=True
            )

    return {
        "tenants_processed": len(results),
        "skipped_non_crm": skipped,
        "schedules_run": len(schedules),
        "results": results,
        "ran_at": datetime.utcnow().isoformat(),
    }


@shared_task(name="apps.workers.tasks.exports.daily_scheduled_reports")
def daily_scheduled_reports() -> dict:
    """Celery entry point for the daily scheduled reports beat task."""
    return asyncio.run(_run_daily_scheduled_reports())
