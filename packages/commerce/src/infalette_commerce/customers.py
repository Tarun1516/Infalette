"""Customer identity resolution across channels.

Implements requirements §3 CRM: "represent a person across website,
Instagram and WhatsApp where identity can be lawfully matched".
Matching order: tenant-scoped email exact -> phone exact -> create.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.customer import Customer


async def find_or_create_customer(
    tenant_id: UUID,
    session: AsyncSession,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> Customer:
    """Find an existing customer by email, else by phone; else create.

    When matched by phone but the stored record lacks an email, the new
    email is backfilled (and vice-versa) so profiles converge instead of
    duplicating.
    """
    customer = None

    if email:
        result = await session.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.email == email,
            )
        )
        customer = result.scalar_one_or_none()

    if customer is None and phone:
        result = await session.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.phone == phone,
            )
        )
        customer = result.scalar_one_or_none()
        if customer is not None and email and not customer.email:
            # Backfill email on phone match (profile convergence)
            customer.email = email
            await session.flush()

    if customer is None and email:
        # Email exists under a different phone: backfill phone
        result = await session.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.email == email,
            )
        )
        customer = result.scalar_one_or_none()

    if customer is not None:
        if phone and not customer.phone:
            customer.phone = phone
            await session.flush()
        if first_name and not customer.first_name:
            customer.first_name = first_name
        if last_name and not customer.last_name:
            customer.last_name = last_name
        return customer

    customer = Customer(
        tenant_id=tenant_id,
        email=email or None,
        phone=phone or None,
        first_name=first_name or None,
        last_name=last_name or None,
        status="active",
    )
    session.add(customer)
    await session.flush()
    return customer
