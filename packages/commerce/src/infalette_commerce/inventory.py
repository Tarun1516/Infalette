"""Transaction-safe inventory management."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.product import Product

logger = logging.getLogger(__name__)


def _get_inventory(product) -> int:
    """Get available inventory quantity with fallback for legacy column name."""
    # Prefer inventory_quantity (DB schema) fallback to inventory (legacy model)
    val = getattr(product, "inventory_quantity", None)
    if val is None:
        val = getattr(product, "inventory", 0)
    return int(val) if val is not None else 0


def _set_inventory(product, value: int) -> None:
    """Set inventory on product handling both inventory_quantity and legacy inventory."""
    if hasattr(product, "inventory_quantity"):
        try:
            product.inventory_quantity = value
        except Exception:
            pass
    if hasattr(product, "inventory"):
        try:
            product.inventory = value
        except Exception:
            pass


async def reserve_inventory(
    product_id: UUID,
    quantity: int,
    session: AsyncSession,
    variant_id: UUID | None = None,
) -> bool:
    """Reserve inventory atomically.

    Variant-aware: when ``variant_id`` is supplied and the variant tracks
    its own stock, the deduction hits the variant row; the parent product
    is adjusted alongside so aggregate counts stay consistent.
    NOTE: performs no commit — callers compose multiple reserves in one
    transaction and commit once (or roll back) for atomicity.
    """
    if variant_id is not None:
        from infalette_database.models.product import ProductVariant

        result = await session.execute(
            select(ProductVariant)
            .where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id)
            .with_for_update()
        )
        variant = result.scalar_one_or_none()
        if variant is not None:
            available = int(getattr(variant, "inventory", 0) or 0)
            policy = getattr(variant, "inventory_policy", "deny")
            if available < quantity and policy != "continue":
                return False
            setattr(
                variant,
                "inventory",
                max(available - quantity, 0) if policy != "continue" else available - quantity,
            )
            # Mirror the deduction on the parent product
            result = await session.execute(
                select(Product).where(Product.id == product_id).with_for_update()
            )
            product = result.scalar_one_or_none()
            if product is not None and getattr(product, "inventory_track", True):
                _set_inventory(product, _get_inventory(product) - quantity)
            return True
        # Variant missing -> fall through to product-level reserve

    return await _reserve_product(product_id, quantity, session)


async def _reserve_product(product_id: UUID, quantity: int, session: AsyncSession) -> bool:
    """Product-level reserve (no commit)."""
    result = await session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    product = result.scalar_one_or_none()
    if not product:
        return False
    available = _get_inventory(product)
    # Respect inventory_track flag if present: if inventory_track is False, always allow
    inventory_track = getattr(product, "inventory_track", True)
    if inventory_track is False:
        # Do not deduct when tracking disabled, but consider reserved
        return True
    # Check inventory_policy: if "continue" allow negative? Default "deny"
    inventory_policy = getattr(product, "inventory_policy", "deny")
    if available < quantity and inventory_policy != "continue":
        return False
    new_val = max(available - quantity, 0) if inventory_policy != "continue" else available - quantity
    _set_inventory(product, new_val)
    return True


async def reserve_inventory_atomic(
    items: list,
    session: AsyncSession,
) -> bool:
    """Reserve all items in ONE transaction; compensate on any failure.

    ``items`` is a list of (product_id, quantity, variant_id). If any
    reservation fails, every earlier deduction in this call is released
    before returning False — spec §3: "Inventory changes must be
    transaction-safe."
    """
    reserved: list = []
    for product_id, quantity, variant_id in items:
        ok = await reserve_inventory(product_id, quantity, session, variant_id=variant_id)
        if not ok:
            for r_product, r_qty, r_variant in reversed(reserved):
                try:
                    await release_inventory(r_product, r_qty, session, variant_id=r_variant)
                except Exception:
                    pass
            return False
        reserved.append((product_id, quantity, variant_id))
    return True


async def release_inventory(
    product_id: UUID,
    quantity: int,
    session: AsyncSession,
    variant_id: UUID | None = None,
) -> None:
    """Release reserved inventory (variant-aware)."""
    # Variant-level release first: restock the variant row and mirror on parent
    if variant_id is not None:
        from infalette_database.models.product import ProductVariant

        result = await session.execute(
            select(ProductVariant)
            .where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id)
            .with_for_update()
        )
        variant = result.scalar_one_or_none()
        if variant is not None:
            setattr(variant, "inventory", int(getattr(variant, "inventory", 0) or 0) + quantity)
            result = await session.execute(
                select(Product).where(Product.id == product_id).with_for_update()
            )
            product = result.scalar_one_or_none()
            if product is not None:
                _set_inventory(product, _get_inventory(product) + quantity)
            await session.flush()
            return

    # Try row-level lock and object mutation to keep both columns in sync
    result = await session.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    product = result.scalar_one_or_none()
    if product is not None:
        # Use helper to handle fallback (flush, not commit — caller owns the txn)
        current = _get_inventory(product)
        new_val = current + quantity
        _set_inventory(product, new_val)
        await session.flush()
        return
    # Fallback to direct update if product not found via select (edge case)
    try:
        if hasattr(Product, "inventory_quantity"):
            await session.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(inventory_quantity=Product.inventory_quantity + quantity)
            )
        if hasattr(Product, "inventory"):
            await session.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(inventory=Product.inventory + quantity)
            )
    except Exception as exc:
        logger.warning("release_inventory fallback update failed for %s: %s", product_id, exc)


async def confirm_inventory_deduction(product_id: UUID, quantity: int, session: AsyncSession) -> None:
    """Confirm inventory deduction after payment.

    Inventory is already deducted at reserve time (see reserve_inventory).
    This is a no-op that logs confirmation and emits an ``inventory.confirmed`` event.
    """
    logger.info(
        "inventory.confirmed: product %s quantity %s already deducted at reserve time",
        product_id,
        quantity,
    )
    # Emit inventory.confirmed event if possible (best-effort)
    try:
        result = await session.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        tenant_id = getattr(product, "tenant_id", None) if product else None
        if tenant_id:
            # Try to record via event bus; avoid hard failure if imports unavailable
            try:
                from infalette_analytics.event_bus import record_event

                await record_event(
                    tenant_id=tenant_id,
                    actor_id=None,
                    event_type="inventory.confirmed",
                    payload={"product_id": str(product_id), "quantity": quantity},
                    session=session,
                )
                # record_event commits; if it does, we are done
                return
            except Exception as e:
                logger.debug("record_event failed for inventory.confirmed: %s", e)
            # Fallback: direct Event insertion
            try:
                from infalette_database.models.event import Event
                from datetime import datetime

                event = Event(
                    tenant_id=tenant_id,
                    actor_id=None,
                    event_type="inventory.confirmed",
                    payload_json={"product_id": str(product_id), "quantity": quantity},
                )
                # Support both possible column names: payload_json vs payload vs type
                # Event model uses payload_json and type/payload variations; set both if present
                if not hasattr(event, "payload_json") and hasattr(event, "payload"):
                    event.payload = {"product_id": str(product_id), "quantity": quantity}
                session.add(event)
                await session.commit()
            except Exception as e2:
                logger.debug("direct Event insert failed for inventory.confirmed: %s", e2)
                try:
                    await session.rollback()
                except Exception:
                    pass
    except Exception as outer:
        logger.debug("confirm_inventory_deduction tenant lookup failed: %s", outer)


async def get_available_inventory(product_id: UUID, session: AsyncSession) -> int:
    """Get available inventory."""
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return 0
    # Respect inventory_track: if disabled, return large number or current
    inventory_track = getattr(product, "inventory_track", True)
    if inventory_track is False:
        return _get_inventory(product)
    return _get_inventory(product)
