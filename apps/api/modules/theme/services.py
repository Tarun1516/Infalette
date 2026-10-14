"""Theme management services."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.theme import Theme
from infalette_database.models.store import Store


# Presets mirrored from packages/themes/src/index.ts
# These are the 3 theme presets requested: default, minimal, vibrant
THEME_PRESETS = [
    {
        "slug": "default",
        "name": "Default",
        "is_preset": True,
        "config_json": {
            "colors": {
                "primary": "#6366f1",
                "primaryForeground": "#ffffff",
                "secondary": "#8b5cf6",
                "secondaryForeground": "#ffffff",
                "background": "#ffffff",
                "foreground": "#1f2937",
                "muted": "#f3f4f6",
                "mutedForeground": "#6b7280",
                "accent": "#ec4899",
                "accentForeground": "#ffffff",
                "destructive": "#ef4444",
                "destructiveForeground": "#ffffff",
                "border": "#e5e7eb",
                "input": "#e5e7eb",
                "ring": "#6366f1",
            },
            "typography": {
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": {
                    "xs": "0.75rem",
                    "sm": "0.875rem",
                    "base": "1rem",
                    "lg": "1.125rem",
                    "xl": "1.25rem",
                    "2xl": "1.5rem",
                    "3xl": "1.875rem",
                    "4xl": "2.25rem",
                },
                "fontWeight": {"normal": 400, "medium": 500, "semibold": 600, "bold": 700},
                "lineHeight": {"tight": 1.25, "normal": 1.5, "relaxed": 1.75},
            },
            "spacing": {"px": "1rem", "py": "1rem", "gap": {"sm": "0.5rem", "md": "1rem", "lg": "1.5rem", "xl": "2rem"}},
            "borderRadius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem", "full": "9999px"},
            "shadows": {
                "sm": "0 1px 2px 0 rgba(0,0,0,0.05)",
                "md": "0 4px 6px -1px rgba(0,0,0,0.1)",
                "lg": "0 10px 15px -3px rgba(0,0,0,0.1)",
                "xl": "0 20px 25px -5px rgba(0,0,0,0.1)",
            },
            "breakpoints": {"sm": "640px", "md": "768px", "lg": "1024px", "xl": "1280px", "2xl": "1536px"},
        },
    },
    {
        "slug": "minimal",
        "name": "Minimal",
        "is_preset": True,
        "config_json": {
            "colors": {
                "primary": "#000000",
                "primaryForeground": "#ffffff",
                "secondary": "#374151",
                "secondaryForeground": "#ffffff",
                "background": "#ffffff",
                "foreground": "#1f2937",
                "muted": "#f3f4f6",
                "mutedForeground": "#6b7280",
                "accent": "#6b7280",
                "accentForeground": "#ffffff",
                "destructive": "#ef4444",
                "destructiveForeground": "#ffffff",
                "border": "#e5e7eb",
                "input": "#e5e7eb",
                "ring": "#6366f1",
            },
            "typography": {
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": {
                    "xs": "0.75rem",
                    "sm": "0.875rem",
                    "base": "1rem",
                    "lg": "1.125rem",
                    "xl": "1.25rem",
                    "2xl": "1.5rem",
                    "3xl": "1.875rem",
                    "4xl": "2.25rem",
                },
                "fontWeight": {"normal": 400, "medium": 500, "semibold": 600, "bold": 700},
                "lineHeight": {"tight": 1.25, "normal": 1.5, "relaxed": 1.75},
            },
            "spacing": {"px": "1rem", "py": "1rem", "gap": {"sm": "0.5rem", "md": "1rem", "lg": "1.5rem", "xl": "2rem"}},
            "borderRadius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem", "full": "9999px"},
            "shadows": {
                "sm": "0 1px 2px 0 rgba(0,0,0,0.05)",
                "md": "0 4px 6px -1px rgba(0,0,0,0.1)",
                "lg": "0 10px 15px -3px rgba(0,0,0,0.1)",
                "xl": "0 20px 25px -5px rgba(0,0,0,0.1)",
            },
            "breakpoints": {"sm": "640px", "md": "768px", "lg": "1024px", "xl": "1280px", "2xl": "1536px"},
        },
    },
    {
        "slug": "vibrant",
        "name": "Vibrant",
        "is_preset": True,
        "config_json": {
            "colors": {
                "primary": "#ec4899",
                "primaryForeground": "#ffffff",
                "secondary": "#f59e0b",
                "secondaryForeground": "#ffffff",
                "background": "#ffffff",
                "foreground": "#1f2937",
                "muted": "#f3f4f6",
                "mutedForeground": "#6b7280",
                "accent": "#10b981",
                "accentForeground": "#ffffff",
                "destructive": "#ef4444",
                "destructiveForeground": "#ffffff",
                "border": "#e5e7eb",
                "input": "#e5e7eb",
                "ring": "#6366f1",
            },
            "typography": {
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": {
                    "xs": "0.75rem",
                    "sm": "0.875rem",
                    "base": "1rem",
                    "lg": "1.125rem",
                    "xl": "1.25rem",
                    "2xl": "1.5rem",
                    "3xl": "1.875rem",
                    "4xl": "2.25rem",
                },
                "fontWeight": {"normal": 400, "medium": 500, "semibold": 600, "bold": 700},
                "lineHeight": {"tight": 1.25, "normal": 1.5, "relaxed": 1.75},
            },
            "spacing": {"px": "1rem", "py": "1rem", "gap": {"sm": "0.5rem", "md": "1rem", "lg": "1.5rem", "xl": "2rem"}},
            "borderRadius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem", "full": "9999px"},
            "shadows": {
                "sm": "0 1px 2px 0 rgba(0,0,0,0.05)",
                "md": "0 4px 6px -1px rgba(0,0,0,0.1)",
                "lg": "0 10px 15px -3px rgba(0,0,0,0.1)",
                "xl": "0 20px 25px -5px rgba(0,0,0,0.1)",
            },
            "breakpoints": {"sm": "640px", "md": "768px", "lg": "1024px", "xl": "1280px", "2xl": "1536px"},
        },
    },
]


async def list_themes(
    tenant_id: UUID,
    session: AsyncSession,
) -> list[Theme]:
    """List themes for a tenant."""
    result = await session.execute(select(Theme).where(Theme.tenant_id == tenant_id))
    return list(result.scalars().all())


async def get_theme(
    tenant_id: UUID,
    theme_id: UUID,
    session: AsyncSession,
) -> Theme | None:
    """Get a theme by ID."""
    result = await session.execute(
        select(Theme).where(Theme.id == theme_id, Theme.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_theme(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Theme:
    """Create a new theme."""
    slug = data.get("slug")
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not slug:
        slug = name.lower().replace(" ", "-").replace("_", "-")

    # If is_default true, clear other defaults
    is_default = data.get("is_default", False)
    if is_default:
        await session.execute(
            update(Theme)
            .where(Theme.tenant_id == tenant_id, Theme.is_default == True)  # noqa: E712
            .values(is_default=False)
            .execution_options(synchronize_session="fetch")
        )

    theme = Theme(
        tenant_id=tenant_id,
        name=name,
        slug=slug,
        config_json=data.get("config_json") or data.get("config") or {},
        is_default=is_default,
    )
    session.add(theme)
    await session.commit()
    await session.refresh(theme)
    return theme


async def update_theme(
    tenant_id: UUID,
    theme_id: UUID,
    data: dict,
    session: AsyncSession,
) -> Theme | None:
    """Update a theme."""
    theme = await get_theme(tenant_id, theme_id, session)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    if data.get("is_default") and not theme.is_default:
        await session.execute(
            update(Theme)
            .where(Theme.tenant_id == tenant_id, Theme.is_default == True)  # noqa: E712
            .values(is_default=False)
            .execution_options(synchronize_session="fetch")
        )

    for key in ["name", "slug", "config_json", "config", "is_default"]:
        if key in data and data[key] is not None:
            if key == "config":
                theme.config_json = data[key]
            else:
                setattr(theme, key, data[key])

    await session.commit()
    await session.refresh(theme)
    return theme


async def delete_theme(
    tenant_id: UUID,
    theme_id: UUID,
    session: AsyncSession,
) -> None:
    """Delete a theme."""
    await session.execute(
        delete(Theme).where(Theme.id == theme_id, Theme.tenant_id == tenant_id)
    )
    await session.commit()


async def get_presets() -> list[dict]:
    """Return 3 theme presets from packages/themes."""
    return THEME_PRESETS


async def apply_theme(
    tenant_id: UUID,
    data: dict,
    session: AsyncSession,
) -> dict:
    """Apply a theme (or preset) to a store.

    Expected data: { "store_id": UUID, "theme_id": UUID } or { "store_id": UUID, "preset": "default"|"minimal"|"vibrant" }
    """
    store_id = data.get("store_id")
    theme_id = data.get("theme_id")
    preset_slug = data.get("preset") or data.get("preset_slug")

    if not store_id:
        raise HTTPException(status_code=400, detail="store_id is required")
    try:
        store_uuid = UUID(str(store_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid store_id")

    # Fetch store tenant-scoped
    result = await session.execute(
        select(Store).where(Store.id == store_uuid, Store.tenant_id == tenant_id)
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    config = None
    theme = None

    if preset_slug:
        preset = next((p for p in THEME_PRESETS if p["slug"] == preset_slug), None)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset {preset_slug} not found")
        config = preset["config_json"]
        # Optionally create or find a Theme record for this preset
        # Check if preset theme exists for tenant, else create
        result = await session.execute(
            select(Theme).where(Theme.tenant_id == tenant_id, Theme.slug == preset_slug)
        )
        theme = result.scalar_one_or_none()
        if not theme:
            theme = Theme(
                tenant_id=tenant_id,
                name=preset["name"],
                slug=preset["slug"],
                config_json=config,
                is_default=False,
            )
            session.add(theme)
            await session.flush()
    elif theme_id:
        try:
            theme_uuid = UUID(str(theme_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid theme_id")
        theme = await get_theme(tenant_id, theme_uuid, session)
        if not theme:
            raise HTTPException(status_code=404, detail="Theme not found")
        config = theme.config_json
    else:
        raise HTTPException(status_code=400, detail="theme_id or preset is required")

    # Apply to store
    store.theme_id = theme.id
    # If Store has theme_config column (check), optionally set
    if hasattr(store, "theme_config"):
        store.theme_config = config
    elif hasattr(store, "config_json"):
        store.config_json = config

    await session.commit()
    await session.refresh(store)

    return {
        "store_id": str(store.id),
        "theme_id": str(theme.id),
        "preset": preset_slug,
        "config": config,
        "message": "Theme applied",
    }
