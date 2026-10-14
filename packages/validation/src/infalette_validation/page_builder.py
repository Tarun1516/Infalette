"""Page builder block schemas and validation."""

from __future__ import annotations

import enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PageBlockType(str, enum.Enum):
    """Page block type enum."""

    HERO = "hero"
    FEATURED_PRODUCTS = "featured_products"
    CATEGORY_GRID = "category_grid"
    TESTIMONIALS = "testimonials"
    INFLUENCER_STORY = "influencer_story"
    VIDEO = "video"
    FAQ = "faq"
    BUNDLES = "bundles"
    NEWSLETTER = "newsletter"
    INSTAGRAM_GALLERY = "instagram_gallery"


class PageBlock(BaseModel):
    """Page block schema.

    Clients configure blocks but cannot insert arbitrary code.
    """

    model_config = {"from_attributes": True, "use_enum_values": True}

    type: PageBlockType
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_block_data(self) -> "PageBlock":
        """Validate block data based on block type."""
        block_type = self.type
        data = self.data

        if block_type == PageBlockType.HERO:
            if "title" not in data:
                raise ValueError("Hero block requires 'title'")
            if "cta_text" not in data:
                raise ValueError("Hero block requires 'cta_text'")

        elif block_type == PageBlockType.FEATURED_PRODUCTS:
            if "product_ids" not in data:
                raise ValueError("Featured products block requires 'product_ids'")
            if not isinstance(data["product_ids"], list):
                raise ValueError("product_ids must be a list")

        elif block_type == PageBlockType.CATEGORY_GRID:
            if "category_ids" not in data:
                raise ValueError("Category grid block requires 'category_ids'")

        elif block_type == PageBlockType.TESTIMONIALS:
            if "testimonials" not in data:
                raise ValueError("Testimonials block requires 'testimonials'")

        elif block_type == PageBlockType.VIDEO:
            if "video_url" not in data:
                raise ValueError("Video block requires 'video_url'")

        elif block_type == PageBlockType.FAQ:
            if "faqs" not in data:
                raise ValueError("FAQ block requires 'faqs'")

        elif block_type == PageBlockType.INSTAGRAM_GALLERY:
            if "instagram_username" not in data:
                raise ValueError("Instagram gallery block requires 'instagram_username'")

        elif block_type == PageBlockType.NEWSLETTER:
            if "form_action" not in data:
                raise ValueError("Newsletter block requires 'form_action'")

        return self


class PageBlockSchema(BaseModel):
    """Schema for a list of page blocks."""

    model_config = {"from_attributes": True, "use_enum_values": True}

    blocks: list[PageBlock] = Field(default_factory=list)


def validate_page_blocks(blocks: list[dict[str, Any]]) -> list[PageBlock]:
    """Validate a list of page block dictionaries.

    Args:
        blocks: List of block dictionaries with 'type' and 'data' keys.

    Returns:
        List of validated PageBlock objects.

    Raises:
        ValueError: If any block is invalid.
    """
    validated = []
    for block_data in blocks:
        validated.append(PageBlock(**block_data))
    return validated
