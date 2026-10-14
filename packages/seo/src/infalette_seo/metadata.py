"""SEO metadata generation."""

from __future__ import annotations


def generate_product_metadata(product, tenant) -> dict:
    """Generate SEO metadata for a product."""
    return {
        "title": f"{product.name} | {tenant.name}",
        "description": product.description or "",
        "canonical": f"https://{tenant.slug}.infalette.com/products/{product.slug}",
        "og:title": product.name,
        "og:description": product.description or "",
    }


def generate_store_metadata(store, tenant) -> dict:
    """Generate SEO metadata for a store."""
    return {
        "title": f"{store.name} | {tenant.name}",
        "description": store.description or "",
        "canonical": f"https://{tenant.slug}.infalette.com",
    }


def generate_page_metadata(page, tenant) -> dict:
    """Generate SEO metadata for a page."""
    return {
        "title": page.title,
        "description": "",
        "canonical": f"https://{tenant.slug}.infalette.com/{page.path}",
    }
