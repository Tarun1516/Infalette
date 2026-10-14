"""Payment processing and reconciliation task."""

from __future__ import annotations

import asyncio
from celery import shared_task


import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.payment import Payment, PaymentStatus
from infalette_database.models.order import Order, OrderStatus
from infalette_integrations.razorpay.client import RazorpayClient
from infalette_integrations.stripe.client import StripeClient

logger = logging.getLogger(__name__)


async def reconcile_payments(
    session: AsyncSession,
    tenant_id: UUID = None,
    provider: str = None,
    days: int = 1,
) -> dict:
    """Reconcile payments with payment providers."""
    cutoff_time = datetime.utcnow() - timedelta(days=days)

    query = select(Payment).where(
        Payment.status == PaymentStatus.PENDING,
        Payment.created_at >= cutoff_time,
    )
    if tenant_id:
        query = query.where(Payment.tenant_id == tenant_id)
    if provider:
        query = query.where(Payment.provider == provider)

    result = await session.execute(query)
    payments = list(result.scalars().all())

    razorpay = RazorpayClient()
    stripe = StripeClient()
    reconciled = 0
    errors = 0

    for payment in payments:
        try:
            if payment.provider.value == "razorpay":
                status = await razorpay.verify_payment(payment.provider_payment_id)
            elif payment.provider.value == "stripe":
                status = await stripe.verify_payment(payment.provider_payment_id)
            else:
                continue

            if status.get("status") in ("captured", "succeeded", "paid"):
                payment.status = PaymentStatus.SUCCEEDED

                # Update order status
                if payment.order_id:
                    await session.execute(
                        __import__("sqlalchemy").update(Order)
                        .where(Order.id == payment.order_id)
                        .values(status=OrderStatus.CONFIRMED)
                        .execution_options(synchronize_session="fetch")
                    )
                reconciled += 1
        except Exception as e:
            logger.error(f"Error reconciling payment {payment.id}: {e}", exc_info=True)
            errors += 1

    await session.commit()

    return {
        "payments_processed": len(payments),
        "reconciled": reconciled,
        "errors": errors,
    }


async def process_refund(
    session: AsyncSession,
    payment_id: UUID,
    amount_cents: int,
    reason: str = None,
) -> dict:
    """Process a refund for a payment."""
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        return {"status": "error", "error": "Payment not found"}

    if payment.provider.value == "razorpay":
        refund = await RazorpayClient().create_refund(
            payment.provider_payment_id, amount_cents, reason
        )
    elif payment.provider.value == "stripe":
        refund = await StripeClient().create_refund(
            payment.provider_payment_id, amount_cents, reason
        )
    else:
        return {"status": "error", "error": "Unsupported provider"}

    if amount_cents >= payment.amount_cents:
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED

    await session.commit()

    return {
        "status": "refunded",
        "payment_id": str(payment_id),
        "amount_cents": amount_cents,
        "refund_id": refund.get("id"),
    }


@shared_task(name="apps.workers.tasks.payments.reconcile_payments")
def reconcile_payments_task(tenant_id: str = None, provider: str = None, days: int = 1) -> dict:
    """Celery entry point: reconcile pending payments against providers."""
    from infalette_database.session import get_session_factory

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as session:
            tid = UUID(tenant_id) if tenant_id else None
            return await reconcile_payments(session, tenant_id=tid, provider=provider, days=days)

    return asyncio.run(_run())
