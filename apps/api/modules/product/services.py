"""Product management services."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infalette_database.models.product import Product, ProductStatus, ProductVariant
from infalette_validation.schemas import ProductCreate


def serialize_product(product: Product) -> dict:
    """Map an ORM Product onto the ProductRead shape.

    The ORM stores images as ``images_json`` / ``image_url`` /
    ``gallery_urls``; ProductRead expects a flat ``images`` list.
    """
    status = getattr(product.status, "value", product.status)
    images = list(getattr(product, "images_json", None) or [])
    if not images:
        images = list(getattr(product, "gallery_urls", None) or [])
    if not images and getattr(product, "image_url", None):
        images = [product.image_url]
    inventory = getattr(product, "inventory_quantity", None)
    if inventory is None:
        inventory = getattr(product, "inventory", 0)
    return {
        "id": str(product.id),
        "tenant_id": str(product.tenant_id),
        "name": product.name,
        "slug": product.slug,
        "sku": product.sku,
        "price_cents": product.price_cents,
        "sale_price_cents": product.sale_price_cents,
        "inventory": int(inventory or 0),
        "images": images,
        "status": status,
        "description": getattr(product, "description", None),
        "tax_class": getattr(product, "tax_class", "standard"),
        "ingredients": getattr(product, "ingredients", None),
        "safety_info": getattr(product, "safety_info", None),
        "age_suitability": getattr(
            getattr(product, "age_suitability", None), "value", None
        ),
        "pregnancy_stage": getattr(
            getattr(product, "pregnancy_stage", None), "value", None
        ),
        "meta_title": getattr(product, "meta_title", None),
        "meta_description": getattr(product, "meta_description", None),
        "image_url": getattr(product, "image_url", None),
        "created_at": getattr(product, "created_at", None),
        "updated_at": getattr(product, "updated_at", None),
    }


def _csv_int(value) -> int | None:
    """Parse an int-ish CSV cell (handles '1,299.00' and empty)."""
    if value is None:
        return None
    raw = str(value).strip().replace(",", "")
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _csv_price_cents(row: dict, cents_key: str, rupees_key: str) -> int | None:
    """Price cell in cents, or rupees converted to cents."""
    cents = _csv_int(row.get(cents_key))
    if cents is not None:
        return cents
    rupees = _csv_int(row.get(rupees_key))
    if rupees is not None:
        return rupees * 100
    return None


async def import_products_csv(tenant_id: UUID, content: str | bytes, session: AsyncSession) -> dict:
    """Bulk import / update products from CSV (onboarding "imports products").

    CSV columns (header row required):
      name, sku, price (rupees) or price_cents, sale_price (rupees) or
      sale_price_cents, inventory, description, tax_class, ingredients,
      safety_info, age_suitability, pregnancy_stage, image_url

    Rows are upserted by SKU within the tenant: existing SKUs are updated,
    new SKUs are created. Honours the tenant's plan product quota.

    Returns {"created": n, "updated": n, "skipped": n, "errors": [...]}.
    """
    import csv
    import io

    from apps.api.core.feature_flags import get_tenant_plan, get_plan_quota

    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", "replace")

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header row")

    # Plan quota on total products (None = unlimited)
    plan = await get_tenant_plan(tenant_id, session)
    quota = get_plan_quota(plan, "products")

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    seen_skus: set[str] = set()

    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        sku = (row.get("sku") or "").strip()
        if not any((v or "").strip() for v in row.values()):
            continue  # truly blank line
        if not name or not sku:
            stats["skipped"] += 1
            stats["errors"].append(f"line {line_no}: name and sku are required")
            continue
        if sku in seen_skus:
            stats["skipped"] += 1
            stats["errors"].append(f"line {line_no}: duplicate sku {sku} in file")
            continue
        seen_skus.add(sku)

        price_cents = _csv_price_cents(row, "price_cents", "price")
        if price_cents is None:
            stats["skipped"] += 1
            stats["errors"].append(f"line {line_no}: price or price_cents required")
            continue
        sale_price_cents = _csv_price_cents(row, "sale_price_cents", "sale_price")

        if quota is not None:
            current_total = stats["created"] + stats["updated"] + len(
                (
                    await session.execute(
                        select(Product).where(Product.tenant_id == tenant_id)
                    )
                ).scalars().all()
            )
            if current_total >= quota:
                stats["errors"].append(
                    f"line {line_no}: plan product quota reached ({quota}); row skipped"
                )
                stats["skipped"] += 1
                continue

        existing = (
            await session.execute(
                select(Product).where(
                    Product.tenant_id == tenant_id, Product.sku == sku
                )
            )
        ).scalar_one_or_none()

        fields = dict(
            name=name,
            price_cents=price_cents,
            sale_price_cents=sale_price_cents,
            inventory=_csv_int(row.get("inventory")) or 0,
            description=(row.get("description") or "").strip() or None,
            tax_class=(row.get("tax_class") or "").strip() or "standard",
            ingredients=(row.get("ingredients") or "").strip() or None,
            safety_info=(row.get("safety_info") or "").strip() or None,
        )
        # Enum fields: keep only if valid (products remain spec-compliant)
        for field, allowed in (
            ("age_suitability", {"newborn", "infant", "toddler", "child", "all"}),
            (
                "pregnancy_stage",
                {
                    "preconception",
                    "pregnancy_first_trimester",
                    "pregnancy_second_trimester",
                    "pregnancy_third_trimester",
                    "postpartum",
                    "newborn",
                    "infant",
                    "toddler",
                },
            ),
        ):
            raw = (row.get(field) or "").strip().lower()
            if raw and raw in allowed:
                fields[field] = raw

        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            stats["updated"] += 1
        else:
            product = Product(
                tenant_id=tenant_id,
                sku=sku,
                slug=name.lower().replace(" ", "-").replace("_", "-") + f"-{uuid4().hex[:4]}",
                images_json=[u] if (u := (row.get("image_url") or "").strip()) else [],
                status=ProductStatus.ACTIVE,
                **fields,
            )
            session.add(product)
            stats["created"] += 1

    await session.commit()
    return stats


async def create_product(tenant_id: UUID, data: ProductCreate, session: AsyncSession) -> Product:
    """Create a new product."""
    slug = data.slug or data.name.lower().replace(" ", "-").replace("_", "-")
    product = Product(
        tenant_id=tenant_id,
        name=data.name,
        slug=slug,
        description=data.description,
        sku=data.sku,
        price_cents=data.price_cents,
        sale_price_cents=data.sale_price_cents,
        tax_class=data.tax_class,
        inventory=data.inventory,
        images_json=data.images,
        ingredients=data.ingredients,
        safety_info=data.safety_info,
        age_suitability=data.age_suitability,
        pregnancy_stage=data.pregnancy_stage,
        status=ProductStatus.ACTIVE,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return serialize_product(product)


async def get_product(tenant_id: UUID, product_id: UUID, session: AsyncSession):
    """Get a product by ID (serialized)."""
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return serialize_product(row) if row else None


async def list_products(
    tenant_id: UUID,
    session: AsyncSession,
    page: int = 1,
    per_page: int = 50,
    search: str | None = None,
    category_id: UUID | None = None,
) -> dict:
    """List products for a tenant with pagination + search (name/SKU).

    Returns ``{"data": [...], "total": n, "page": p, "per_page": pp}``.
    """
    from sqlalchemy import func as _func, or_ as _or

    query = select(Product).where(Product.tenant_id == tenant_id)
    count_query = select(_func.count(Product.id)).where(Product.tenant_id == tenant_id)
    if search:
        like = f"%{search}%"
        flt = _or(Product.name.ilike(like), Product.sku.ilike(like))
        query = query.where(flt)
        count_query = count_query.where(flt)
    if category_id is not None and hasattr(Product, "category_id"):
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)

    total = (await session.execute(count_query)).scalar() or 0
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    query = (
        query.order_by(Product.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await session.execute(query)).scalars().all()
    return {
        "data": [serialize_product(p) for p in rows],
        "total": int(total),
        "page": page,
        "per_page": per_page,
    }


async def update_product(tenant_id: UUID, product_id: UUID, data: ProductCreate, session: AsyncSession) -> Product | None:
    """Update a product."""
    await session.execute(
        update(Product)
        .where(Product.id == product_id, Product.tenant_id == tenant_id)
        .values(
            name=data.name,
            slug=data.slug,
            description=data.description,
            sku=data.sku,
            price_cents=data.price_cents,
            sale_price_cents=data.sale_price_cents,
            tax_class=data.tax_class,
            inventory=data.inventory,
            images_json=data.images,
            ingredients=data.ingredients,
            safety_info=data.safety_info,
            age_suitability=data.age_suitability,
            pregnancy_stage=data.pregnancy_stage,
        )
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()

    # Spec §4 event model: product.updated
    try:
        from infalette_analytics.event_bus import record_event

        await record_event(
            tenant_id=tenant_id,
            actor_id=None,
            event_type="product.updated",
            payload={"product_id": str(product_id), "name": data.name, "sku": data.sku},
            session=session,
        )
    except Exception:
        pass

    return await get_product(tenant_id, product_id, session)


async def delete_product(tenant_id: UUID, product_id: UUID, session: AsyncSession) -> None:
    """Delete a product."""
    await session.execute(
        delete(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    await session.commit()


async def adjust_stock(
    tenant_id: UUID, product_id: UUID, new_quantity: int, session: AsyncSession
) -> Product | None:
    """Update only the inventory columns on a product.

    Returns the updated product or ``None`` if not found. Both
    ``inventory_quantity`` (canonical) and ``inventory`` (legacy alias)
    are kept in sync so storefront + admin consumers see the same value.
    """
    new_quantity = max(0, int(new_quantity))
    result = await session.execute(
        update(Product)
        .where(Product.id == product_id, Product.tenant_id == tenant_id)
        .values(
            inventory_quantity=new_quantity,
            inventory=new_quantity,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount == 0:
        await session.rollback()
        return None
    await session.commit()
    # Read back to return the canonical row
    fetch = await session.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    return fetch.scalar_one_or_none()


async def search_products(tenant_id: UUID, query: str, session: AsyncSession) -> list[Product]:
    """Search products by name or SKU."""
    result = await session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.name.ilike(f"%{query}%"),
        )
    )
    return list(result.scalars().all())


def serialize_variant(variant: ProductVariant) -> dict:
    """Map an ORM ProductVariant onto a plain dict for responses."""
    return {
        "id": str(variant.id),
        "tenant_id": str(variant.tenant_id),
        "product_id": str(variant.product_id),
        "sku": variant.sku,
        "price_cents": variant.price_cents,
        "sale_price_cents": variant.sale_price_cents,
        "inventory_quantity": getattr(variant, "inventory_quantity", None)
        or getattr(variant, "inventory", 0),
        "dimensions_json": getattr(variant, "dimensions_json", None),
        "created_at": getattr(variant, "created_at", None),
        "updated_at": getattr(variant, "updated_at", None),
    }


async def list_variants(tenant_id: UUID, product_id: UUID, session: AsyncSession) -> list[ProductVariant]:
    """List all variants for a product owned by the tenant."""
    result = await session.execute(
        select(ProductVariant).where(
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.product_id == product_id,
        )
    )
    return [serialize_variant(v) for v in result.scalars().all()]


async def get_variant(
    tenant_id: UUID, product_id: UUID, variant_id: UUID, session: AsyncSession
) -> ProductVariant | None:
    """Get a variant by ID, scoped to the tenant and product."""
    result = await session.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
            ProductVariant.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    return serialize_variant(row) if row else None


async def create_variant(tenant_id: UUID, product_id: UUID, data: dict, session: AsyncSession) -> ProductVariant | None:
    """Create a new variant for a product. Returns None if the product is not found for the tenant."""
    product = await get_product(tenant_id, product_id, session)
    if not product:
        return None

    inventory = data.get("inventory_quantity", data.get("inventory", 0))
    sku = (data.get("sku") or "").strip()
    if not sku:
        n = 1
        existing = await session.execute(select(ProductVariant).where(ProductVariant.sku == f"{product['sku']}-{n}"))
        while existing.scalar_one_or_none():
            n += 1
            existing = await session.execute(select(ProductVariant).where(ProductVariant.sku == f"{product['sku']}-{n}"))
        sku = f"{product['sku']}-{n}"

    from uuid import UUID as _UUID

    variant = ProductVariant(
        tenant_id=tenant_id,
        product_id=_UUID(str(product["id"])),
        sku=sku,
        price_cents=data["price_cents"],
        sale_price_cents=data.get("sale_price_cents"),
        inventory=inventory,
        dimensions_json=data.get("dimensions_json"),
    )
    session.add(variant)
    await session.commit()
    await session.refresh(variant)
    return serialize_variant(variant)


async def update_variant(
    tenant_id: UUID, product_id: UUID, variant_id: UUID, data: dict, session: AsyncSession
) -> ProductVariant | None:
    """Update a variant with a partial dict."""
    variant = await get_variant(tenant_id, product_id, variant_id, session)
    if not variant:
        return None

    field_map = {
        "sku": "sku",
        "price_cents": "price_cents",
        "sale_price_cents": "sale_price_cents",
        "inventory_quantity": "inventory",
        "inventory": "inventory",
        "dimensions_json": "dimensions_json",
    }
    for key, column in field_map.items():
        if key in data and data[key] is not None:
            setattr(variant, column, data[key])

    await session.commit()
    await session.refresh(variant)
    return serialize_variant(variant)


async def delete_variant(tenant_id: UUID, product_id: UUID, variant_id: UUID, session: AsyncSession) -> bool:
    """Delete a variant. Returns False if it was not found."""
    variant = await get_variant(tenant_id, product_id, variant_id, session)
    if not variant:
        return False
    await session.delete(variant)
    await session.commit()
    return True
