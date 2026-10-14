"""Store management services."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.store import Store, StoreStatus
from infalette_validation.schemas import StoreCreate


async def create_store(tenant_id: UUID, data: StoreCreate, session: AsyncSession) -> Store:
    """Create a new store."""
    slug = data.name.lower().replace(" ", "-").replace("_", "-")
    store = Store(
        tenant_id=tenant_id,
        name=data.name,
        slug=slug,
        description=data.description,
        theme_id=data.theme_id,
        status=StoreStatus.DRAFT,
    )
    session.add(store)
    await session.commit()
    await session.refresh(store)
    return store


async def get_store(store_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> Store | None:
    """Get a store by ID with optional tenant isolation."""
    query = select(Store).where(Store.id == store_id)
    if tenant_id is not None:
        query = query.where(Store.tenant_id == tenant_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_stores(tenant_id: UUID, session: AsyncSession) -> list[Store]:
    """List all stores for a tenant."""
    result = await session.execute(select(Store).where(Store.tenant_id == tenant_id))
    return list(result.scalars().all())


async def update_store(store_id: UUID, data: StoreCreate, session: AsyncSession, tenant_id: UUID | None = None) -> Store | None:
    """Update a store with tenant isolation."""
    # Verify ownership first
    existing = await get_store(store_id, session, tenant_id=tenant_id)
    if not existing:
        return None
    await session.execute(
        update(Store)
        .where(Store.id == store_id)
        .values(name=data.name, description=data.description, theme_id=data.theme_id)
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return await get_store(store_id, session, tenant_id=tenant_id)


async def delete_store(store_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> None:
    """Delete a store with tenant isolation."""
    if tenant_id is not None:
        # Ensure belongs to tenant
        existing = await get_store(store_id, session, tenant_id=tenant_id)
        if not existing:
            return
        await session.execute(delete(Store).where(Store.id == store_id, Store.tenant_id == tenant_id))
    else:
        await session.execute(delete(Store).where(Store.id == store_id))
    await session.commit()


async def publish_store(store_id: UUID, session: AsyncSession, tenant_id: UUID | None = None) -> Store | None:
    """Publish a store with tenant isolation."""
    if tenant_id is not None:
        existing = await get_store(store_id, session, tenant_id=tenant_id)
        if not existing:
            return None
    else:
        existing = None
    await session.execute(
        update(Store)
        .where(Store.id == store_id)
        .values(status=StoreStatus.PUBLISHED, published_at=datetime.utcnow())
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    store = await get_store(store_id, session, tenant_id=tenant_id)

    # Spec §4 event model: storefront.published
    try:
        from infalette_analytics.event_bus import record_event

        effective_tenant = tenant_id or getattr(existing, "tenant_id", None) or getattr(store, "tenant_id", None)
        if effective_tenant:
            await record_event(
                tenant_id=effective_tenant,
                actor_id=None,
                event_type="storefront.published",
                payload={
                    "store_id": str(store_id),
                    "custom_domain": getattr(store, "custom_domain", None),
                },
                session=session,
            )
    except Exception:
        pass
    return store


async def get_store_settings(tenant_id: UUID, session: AsyncSession) -> dict | None:
    """Get store settings for tenant (first store with extended dict)."""
    result = await session.execute(select(Store).where(Store.tenant_id == tenant_id))
    store = result.scalars().first()
    if not store:
        return None
    # Build settings dict compatible with admin expectations
    return {
        "id": str(store.id),
        "tenant_id": str(store.tenant_id),
        "name": store.name,
        "slug": store.slug,
        "description": getattr(store, "description", None),
        "theme_id": str(store.theme_id) if getattr(store, "theme_id", None) else None,
        "status": store.status.value if hasattr(store.status, "value") else store.status,
        "published_at": store.published_at.isoformat() if getattr(store, "published_at", None) else None,
        "custom_domain": getattr(store, "custom_domain", None),
        "logo": getattr(store, "logo", None),
        "logo_url": getattr(store, "logo_url", None),
        "theme_config": getattr(store, "theme_config", None) or getattr(store, "config_json", None) or {},
        "currency": getattr(store, "currency", "INR"),
        "tax_rate": getattr(store, "tax_rate", 18),
        "shipping_rules": getattr(store, "shipping_rules_json", None) or {},
        "menus": getattr(store, "menus_json", None) or [],
        "social_links": getattr(store, "social_links_json", None) or {},
        "legal_pages": getattr(store, "legal_pages_json", None) or {},
        "created_at": store.created_at.isoformat() if getattr(store, "created_at", None) else None,
        "updated_at": store.updated_at.isoformat() if getattr(store, "updated_at", None) else None,
        # Also expose store nested for admin handling
        "store": {
            "id": str(store.id),
            "name": store.name,
            "slug": store.slug,
            "description": getattr(store, "description", None),
            "theme_id": str(store.theme_id) if getattr(store, "theme_id", None) else None,
        },
    }


async def update_store_settings(tenant_id: UUID, data: dict, session: AsyncSession) -> dict | None:
    """Update store settings for tenant's first store (create if not exists)."""
    result = await session.execute(select(Store).where(Store.tenant_id == tenant_id))
    store = result.scalars().first()
    if not store:
        # Create default store if none exists
        name = data.get("name", "My Store")
        slug = name.lower().replace(" ", "-").replace("_", "-")
        store = Store(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            description=data.get("description"),
            theme_id=data.get("theme_id"),
            status=StoreStatus.DRAFT,
        )
        # Apply optional fields if present on model
        for field in ["custom_domain", "logo", "logo_url", "currency", "tax_rate", "theme_config", "config_json"]:
            if field in data and hasattr(store, field):
                setattr(store, field, data[field])
        if "theme_config" in data and not hasattr(store, "theme_config") and hasattr(store, "config_json"):
            store.config_json = data["theme_config"]
        session.add(store)
        await session.commit()
        await session.refresh(store)
        return await get_store_settings(tenant_id, session)

    # Update fields
    for key in [
        "name", "slug", "description", "theme_id", "custom_domain", "logo",
        "logo_url", "currency", "tax_rate", "theme_config", "config_json",
        # Tenant-configurable commerce settings (spec §3)
        "shipping_rules_json", "menus_json", "social_links_json", "legal_pages_json",
    ]:
        if key in data and data[key] is not None:
            if hasattr(store, key):
                setattr(store, key, data[key])
            elif key == "theme_config" and hasattr(store, "config_json"):
                store.config_json = data[key]

    # Accept camel-friendly aliases from the admin UI
    alias_map = {
        "shipping_rules": "shipping_rules_json",
        "menus": "menus_json",
        "social_links": "social_links_json",
        "legal_pages": "legal_pages_json",
    }
    for src_key, dest_key in alias_map.items():
        if src_key in data and hasattr(store, dest_key):
            setattr(store, dest_key, data[src_key])

    # Handle theme_config generic
    if "theme_config" in data and not hasattr(store, "theme_config"):
        if hasattr(store, "config_json"):
            store.config_json = data["theme_config"]

    await session.commit()
    await session.refresh(store)
    return await get_store_settings(tenant_id, session)
