"""Shared Pydantic validation schemas."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================

class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class UserRole(str, enum.Enum):
    PLATFORM_OWNER = "platform_owner"
    TENANT_OWNER = "tenant_owner"
    STORE_MANAGER = "store_manager"
    MARKETING_AGENT = "marketing_agent"
    SUPPORT_AGENT = "support_agent"
    CUSTOMER = "customer"


class StoreStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class ProductAgeSuitability(str, enum.Enum):
    NEWBORN = "newborn"
    INFANT = "infant"
    TODDLER = "toddler"
    CHILD = "child"
    ALL = "all"


class ProductPregnancyStage(str, enum.Enum):
    PRECONCEPTION = "preconception"
    PREGNANCY_FIRST_TRIMESTER = "pregnancy_first_trimester"
    PREGNANCY_SECOND_TRIMESTER = "pregnancy_second_trimester"
    PREGNANCY_THIRD_TRIMESTER = "pregnancy_third_trimester"
    POSTPARTUM = "postpartum"
    NEWBORN = "newborn"
    INFANT = "infant"
    TODDLER = "toddler"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    RETURNED = "returned"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentProvider(str, enum.Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    COD = "cod"


class ConversationChannel(str, enum.Enum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"


class LeadStage(str, enum.Enum):
    NEW_LEAD = "new_lead"
    ENGAGED = "engaged"
    PRODUCT_SELECTED = "product_selected"
    CHECKOUT_CREATED = "checkout_created"
    PAID = "paid"
    FULFILLED = "fulfilled"
    REPEAT_CUSTOMER = "repeat_customer"


class LeadSource(str, enum.Enum):
    INSTAGRAM_COMMENT = "instagram_comment"
    INSTAGRAM_DM = "instagram_dm"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    REFERRAL = "referral"
    OTHER = "other"


class AutomationRuleStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class AutomationTriggerType(str, enum.Enum):
    COMMENT_KEYWORD = "comment_keyword"
    DM_PRODUCT_SKU = "dm_product_sku"
    STORY_RESPONSE = "story_response"
    WHATSAPP_FLOW = "whatsapp_flow"
    CHECKOUT_UNPAID = "checkout_unpaid"


class AutomationActionType(str, enum.Enum):
    PRIVATE_REPLY = "private_reply"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    CHECKOUT_LINK = "checkout_link"
    LEAD_CREATE = "lead_create"
    ASSIGN_AGENT = "assign_agent"
    REMINDER_SCHEDULE = "reminder_schedule"
    TAG = "tag"


class CheckoutStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# =============================================================================
# Base Schema
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common fields."""

    model_config = {"from_attributes": True, "use_enum_values": True}


class BaseRead(BaseSchema):
    """Base read schema with id and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Tenant Schemas
# =============================================================================

class TenantCreate(BaseSchema):
    """Schema for creating a tenant."""

    name: str = Field(..., min_length=1, max_length=255)
    plan_id: UUID
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)


class TenantRead(BaseRead):
    """Schema for reading a tenant."""

    name: str
    slug: str
    status: TenantStatus


# =============================================================================
# Store Schemas
# =============================================================================

class StoreCreate(BaseSchema):
    """Schema for creating a store."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    theme_id: Optional[UUID] = None


class StoreRead(BaseRead):
    """Schema for reading a store."""

    tenant_id: UUID
    name: str
    slug: str
    description: Optional[str]
    status: StoreStatus
    published_at: Optional[datetime]


# =============================================================================
# Product Schemas
# =============================================================================

class ProductVariantCreate(BaseSchema):
    """Schema for creating a product variant."""

    sku: str = Field(..., min_length=1, max_length=100)
    price_cents: int = Field(..., ge=0)
    sale_price_cents: Optional[int] = Field(default=None, ge=0)
    inventory: int = Field(default=0, ge=0)


class ProductCreate(BaseSchema):
    """Schema for creating a product."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sku: str = Field(..., min_length=1, max_length=100)
    price_cents: int = Field(..., ge=0)
    sale_price_cents: Optional[int] = Field(default=None, ge=0)
    tax_class: str = Field(default="standard")
    inventory: int = Field(default=0, ge=0)
    images: list[str] = Field(default_factory=list)
    ingredients: Optional[str] = None
    safety_info: Optional[str] = None
    age_suitability: Optional[ProductAgeSuitability] = None
    pregnancy_stage: Optional[ProductPregnancyStage] = None
    category_ids: list[UUID] = Field(default_factory=list)
    variants: list[ProductVariantCreate] = Field(default_factory=list)


class ProductRead(BaseRead):
    """Schema for reading a product."""

    tenant_id: UUID
    name: str
    slug: str
    sku: str
    price_cents: int
    sale_price_cents: Optional[int]
    inventory: int
    images: list[str]
    status: ProductStatus


# =============================================================================
# Cart Schemas
# =============================================================================

class CartItemCreate(BaseSchema):
    """Schema for adding an item to cart."""

    product_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int = Field(..., ge=1)


# =============================================================================
# Checkout Schemas
# =============================================================================

class AddressSchema(BaseSchema):
    """Address schema.

    Storefront forms send ``address``/``pincode``; the canonical field
    names are ``line1``/``postal_code``. A validator normalizes the
    aliases so both client shapes validate.
    """

    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str

    @model_validator(mode="before")
    @classmethod
    def _accept_address_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "line1" not in data and "address" in data:
                data["line1"] = data.pop("address")
            elif "address" in data and data.get("line1") is None:
                data["line1"] = data.get("address")
            if "postal_code" not in data and "pincode" in data:
                data["postal_code"] = data.pop("pincode")
            elif "pincode" in data and data.get("postal_code") is None:
                data["postal_code"] = data.get("pincode")
        return data


class CustomerDataSchema(BaseSchema):
    """Customer data for checkout."""

    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class AttributionSchema(BaseSchema):
    """Marketing attribution captured by the storefront.

    Carries UTM parameters and an optional campaign reference so web
    checkouts attribute like social ones (spec: "attribution coverage
    90%+" and campaign performance reporting).
    """

    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    campaign_id: Optional[UUID] = None
    referrer: Optional[str] = None
    landing_path: Optional[str] = None


class CheckoutCreate(BaseSchema):
    """Schema for creating a checkout."""

    customer_data: CustomerDataSchema
    shipping_address: AddressSchema
    billing_address: AddressSchema
    discount_codes: list[str] = Field(default_factory=list)
    attribution: Optional[AttributionSchema] = None


# =============================================================================
# Order Schemas
# =============================================================================

class OrderRead(BaseRead):
    """Schema for reading an order."""

    tenant_id: UUID
    customer_id: Optional[UUID]
    status: OrderStatus
    total_cents: int
    currency: str
    shipping_address: dict
    billing_address: dict


# =============================================================================
# Lead Schemas
# =============================================================================

class LeadRead(BaseRead):
    """Schema for reading a lead."""

    tenant_id: UUID
    customer_id: UUID
    stage: LeadStage
    source: LeadSource
    campaign_id: Optional[UUID]
    assigned_agent_id: Optional[UUID]


# =============================================================================
# Automation Schemas
# =============================================================================

class AutomationRuleCreate(BaseSchema):
    """Schema for creating an automation rule."""

    name: str = Field(..., min_length=1, max_length=255)
    trigger_type: AutomationTriggerType
    conditions: dict = Field(default_factory=dict)
    actions: list[dict] = Field(default_factory=list)
    status: AutomationRuleStatus = AutomationRuleStatus.DRAFT


# =============================================================================
# Analytics Schemas
# =============================================================================

class EventRead(BaseRead):
    """Schema for reading an event."""

    tenant_id: UUID
    actor_id: Optional[UUID]
    type: str
    payload: dict


class MetricDailyRead(BaseRead):
    """Schema for reading daily metrics."""

    tenant_id: UUID
    date: datetime
    channel: Optional[str]
    product_id: Optional[UUID]
    metrics: dict
