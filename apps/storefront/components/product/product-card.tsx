import Link from "next/link";

/**
 * Product card — Apple-inspired minimalist tile.
 *
 *  - Large product image (1:1) with subtle hover scale.
 *  - Wordmark-like product name, smaller muted price.
 *  - No badges, no decoration — the photo is the hero.
 */
export default function ProductCard({
  product,
  tenant,
}: {
  product: any;
  tenant: string;
}) {
  const price = product.sale_price_cents
    ? product.sale_price_cents / 100
    : product.price_cents / 100;
  const onSale = Boolean(product.sale_price_cents);
  const imgSrc = product.images?.[0] || product.image_url;

  return (
    <Link
      href={`/${tenant}/products/${product.id}`}
      className="group block rounded-2xl bg-white dark:bg-neutral-950 transition-all duration-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.08)] dark:hover:shadow-[0_8px_30px_rgba(255,255,255,0.04)]"
    >
      <div className="aspect-square w-full overflow-hidden rounded-t-2xl bg-gray-100 dark:bg-neutral-900">
        {imgSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imgSrc}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-gray-400">
            No image
          </div>
        )}
      </div>
      <div className="px-4 pt-3 pb-5">
        <p className="text-[15px] font-medium text-gray-900 dark:text-neutral-100 line-clamp-1">
          {product.name}
        </p>
        {product.sku && (
          <p className="mt-0.5 text-[12px] text-gray-400 dark:text-neutral-500">
            {product.sku}
          </p>
        )}
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
            ₹{price.toFixed(2)}
          </span>
          {onSale && (
            <span className="text-[13px] text-gray-400 line-through">
              ₹{(product.price_cents / 100).toFixed(2)}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}