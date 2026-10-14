"""Meta tag generation for SEO."""

from __future__ import annotations

from typing import Optional


class MetaTagGenerator:
    """Generates meta tags for SEO."""

    def generate_meta_tags(self, page_data: dict) -> dict:
        """Generate meta tags for a page."""
        title = page_data.get("title", "")
        description = page_data.get("meta_description", "")
        url = page_data.get("url", "")
        image = page_data.get("image", "")
        keywords = page_data.get("meta_keywords", [])

        tags = {
            "title": title,
            "description": description,
            "canonical": page_data.get("canonical_url", url),
            "og:title": title,
            "og:description": description,
            "og:url": url,
            "og:type": page_data.get("og_type", "website"),
            "og:image": image,
            "twitter:card": "summary_large_image",
            "twitter:title": title,
            "twitter:description": description,
            "twitter:image": image,
        }

        if keywords:
            tags["keywords"] = ", ".join(keywords)

        return tags

    def generate_product_meta_tags(self, product: dict) -> dict:
        """Generate meta tags for a product page."""
        return self.generate_meta_tags({
            "title": f"{product.get('name', '')} | Infalette",
            "meta_description": product.get("description", ""),
            "url": product.get("url", ""),
            "image": product.get("image", ""),
            "og_type": "product",
            "meta_keywords": product.get("tags", []),
        })

    def generate_collection_meta_tags(self, collection: dict) -> dict:
        """Generate meta tags for a collection page."""
        return self.generate_meta_tags({
            "title": f"{collection.get('name', '')} | Infalette",
            "meta_description": collection.get("description", ""),
            "url": collection.get("url", ""),
            "og_type": "website",
        })

    def generate_structured_data(self, page_type: str, data: dict) -> dict:
        """Generate structured data (JSON-LD) for a page."""
        if page_type == "product":
            return {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": data.get("name"),
                "description": data.get("description"),
                "image": data.get("image"),
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": data.get("currency", "INR"),
                    "price": str(data.get("price", 0) / 100),
                    "availability": "https://schema.org/InStock" if data.get("in_stock") else "https://schema.org/OutOfStock",
                },
            }
        elif page_type == "organization":
            return {
                "@context": "https://schema.org/",
                "@type": "Organization",
                "name": data.get("name", "Infalette"),
                "url": data.get("url", "https://infalette.com"),
            }
        return {}
