"use client";

import { useEffect, useState } from "react";
import { storefrontApi, getCartSessionId } from "@/lib/api";
import { notifyCartChanged } from "@/lib/cart-events";
import { toast } from "@/components/toaster";

export default function AddToCart({
  tenant,
  product,
}: {
  tenant: string;
  product: any;
}) {
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const [variants, setVariants] = useState<any[]>([]);
  const [selectedVariant, setSelectedVariant] = useState<string>("");
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [variantError, setVariantError] = useState<string | null>(null);
  const maxQty = Number(product.inventory ?? product.inventory_quantity ?? 99);

  useEffect(() => {
    let cancelled = false;
    setVariantsLoading(true);
    setVariantError(null);
    storefrontApi
      .getProductVariants(tenant, product.id)
      .then((list) => {
        if (cancelled) return;
        setVariants(Array.isArray(list) ? list : []);
        const first = (list as any[]).find((v) => v.is_available !== false) || (list as any[])[0];
        if (first?.id) setSelectedVariant(first.id);
      })
      .catch(() => {
        if (!cancelled) {
          setVariants([]);
          setVariantError(null);
        }
      })
      .finally(() => {
        if (!cancelled) setVariantsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenant, product.id]);

  const hasVariants = variants.length > 0;
  const canAdd = !variantsLoading && (!hasVariants || !!selectedVariant) && maxQty > 0;

  const handleAdd = async () => {
    if (!canAdd) return;
    setAdding(true);
    setAdded(false);
    try {
      await storefrontApi.addToCart(
        tenant,
        product.id,
        quantity,
        hasVariants ? selectedVariant : undefined,
      );
      setAdded(true);
      notifyCartChanged(tenant);
      toast({
        kind: "success",
        title: "Added to bag",
        description: `${product.name} × ${quantity}`,
      });
      void fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/public/track`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Tenant": tenant,
            "X-Cart-Session-ID": getCartSessionId(),
          },
          body: JSON.stringify({
            event_type: "checkout.started",
            product_id: product.id,
            variant_id: hasVariants ? selectedVariant : undefined,
            source: "storefront",
          }),
        }
      ).catch(() => undefined);
    } catch (e: any) {
      toast({ kind: "error", title: "Could not add to bag", description: e?.message });
    } finally {
      setAdding(false);
    }
  };

  const variantLabel = (v: any) => {
    const parts: string[] = [];
    if (v.title) parts.push(v.title);
    if (v.sku) parts.push(`SKU ${v.sku}`);
    const price = v.price_cents ?? v.sale_price_cents;
    if (price != null) parts.push(`₹${(price / 100).toFixed(2)}`);
    return parts.join(" • ");
  };

  return (
    <div>
      {hasVariants && (
        <div className="mb-5">
          <label
            htmlFor="variant-select"
            className="block text-[12px] uppercase tracking-[0.16em] text-gray-500 dark:text-neutral-500 mb-2"
          >
            Variant
          </label>
          <select
            id="variant-select"
            value={selectedVariant}
            onChange={(e) => setSelectedVariant(e.target.value)}
            className="w-full h-11 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {variants.map((v: any) => (
              <option
                key={v.id}
                value={v.id}
                disabled={v.is_available === false || (v.inventory_quantity ?? 0) <= 0}
              >
                {variantLabel(v)}
                {v.is_available === false || (v.inventory_quantity ?? 0) <= 0
                  ? " — unavailable"
                  : ""}
              </option>
            ))}
          </select>
        </div>
      )}
      {variantError && (
        <p className="text-[12px] text-amber-600 mb-2">{variantError}</p>
      )}

      <div className="flex items-stretch gap-2 mb-4">
        <div className="flex items-center gap-2 rounded-full border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-4 h-12">
          <button
            type="button"
            onClick={() => setQuantity(Math.max(1, quantity - 1))}
            className="w-7 h-7 rounded-full text-lg leading-none text-gray-700 dark:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-900"
            aria-label="Decrease"
          >
            −
          </button>
          <span className="w-6 text-center text-[14px]">{quantity}</span>
          <button
            type="button"
            onClick={() => setQuantity(Math.min(maxQty || 999, quantity + 1))}
            className="w-7 h-7 rounded-full text-lg leading-none text-gray-700 dark:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-900"
            aria-label="Increase"
          >
            +
          </button>
        </div>
        <button
          onClick={handleAdd}
          disabled={!canAdd || adding}
          className="flex-1 h-12 inline-flex items-center justify-center rounded-full bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-[15px] font-medium hover:bg-blue-700 transition-colors"
        >
          {adding ? "Adding…" : added ? "Added ✓ — View bag" : "Add to bag"}
        </button>
      </div>
      {added && (
        <a
          href={`/${tenant}/cart`}
          className="block text-center text-[13px] text-blue-600 hover:underline"
        >
          Go to bag →
        </a>
      )}
    </div>
  );
}