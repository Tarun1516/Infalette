"""JSON-LD structured data generation."""

from __future__ import annotations


def generate_product_schema(product, tenant) -> dict:
    """Generate JSON-LD for a product."""
    return {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": product.name,
        "description": product.description or "",
        "sku": product.sku,
        "offers": {
            "@type": "Offer",
            "priceCurrency": "INR",
            "price": str(product.price_cents / 100),
        },
    }


def generate_store_schema(store, tenant) -> dict:
    """Generate JSON-LD for a store."""
    return {
        "@context": "https://schema.org/",
        "@type": "Store",
        "name": store.name,
        "description": store.description or "",
    }


def generate_breadcrumb_schema(items: list[dict]) -> dict:
    """Generate JSON-LD for breadcrumbs."""
    return {
        "@context": "https://schema.org/",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def generate_review_schema(reviews: list[dict]) -> dict:
    """Generate JSON-LD for reviews."""
    return {
        "@context": "https://schema.org/",
        "@type": "Review",
        "reviewList": reviews,
    }
