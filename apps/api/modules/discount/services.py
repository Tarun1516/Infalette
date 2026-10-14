"""Discount code services — tenant-scoped CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.discount_code import DiscountCode


async def list_discounts(tenant_id: UUID, session: AsyncSession, active_only: bool = False):
    q = select(DiscountCode).where(DiscountCode.tenant_id == tenant_id).order_by(DiscountCode.created_at.desc())
    if active_only:
        q = q.where(DiscountCode.is_active == True)  # noqa
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_discount(tenant_id: UUID, discount_id: UUID, session: AsyncSession):
    result = await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id, DiscountCode.tenant_id == tenant_id))
    return result.scalar_one_or_none()


async def create_discount(tenant_id: UUID, data: dict, session: AsyncSession):
    # normalize code upper
    code = (data.get("code") or "").strip().upper()
    if not code:
        raise ValueError("Code is required")
    # unique per tenant
    exists = await session.execute(select(DiscountCode).where(DiscountCode.tenant_id == tenant_id, DiscountCode.code == code))
    if exists.scalar_one_or_none():
        raise ValueError(f"Discount code {code} already exists")
    dc = DiscountCode(
        tenant_id=tenant_id,
        code=code,
        discount_type=data.get("discount_type") or data.get("type") or "percentage",
        value=int(data.get("value", 0)),
        minimum_order_cents=int(data.get("minimum_order_cents", 0) or 0),
        usage_limit=data.get("usage_limit"),
        used_count=0,
        is_active=bool(data.get("is_active", True)),
        expires_at=_parse_dt(data.get("expires_at")),
    )
    session.add(dc)
    await session.commit()
    await session.refresh(dc)
    return dc


async def update_discount(tenant_id: UUID, discount_id: UUID, data: dict, session: AsyncSession):
    dc = await get_discount(tenant_id, discount_id, session)
    if not dc:
        return None
    for field in ["discount_type", "type", "value", "minimum_order_cents", "usage_limit", "is_active", "expires_at", "code"]:
        if field not in data:
            continue
        val = data[field]
        if field in ("type", "discount_type"):
            dc.discount_type = val
        elif field == "code":
            dc.code = str(val).strip().upper()
        elif field == "expires_at":
            dc.expires_at = _parse_dt(val)
        else:
            setattr(dc, field if field != "type" else "discount_type", val)
    await session.commit()
    await session.refresh(dc)
    return dc


async def delete_discount(tenant_id: UUID, discount_id: UUID, session: AsyncSession):
    await session.execute(delete(DiscountCode).where(DiscountCode.id == discount_id, DiscountCode.tenant_id == tenant_id))
    await session.commit()

def _parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    try:
        # handle ISO strings
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None
