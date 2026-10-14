"""Infalette SEO package."""

from infalette_seo.metadata import generate_product_metadata, generate_store_metadata
from infalette_seo.schema import generate_product_schema, generate_store_schema
from infalette_seo.sitemap import generate_sitemap, generate_robots_txt

__all__ = [
    "generate_product_metadata",
    "generate_store_metadata",
    "generate_product_schema",
    "generate_store_schema",
    "generate_sitemap",
    "generate_robots_txt",
]
