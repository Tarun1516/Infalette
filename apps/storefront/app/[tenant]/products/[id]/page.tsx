import { notFound } from "next/navigation";
import Link from "next/link";
import AddToCart from "@/components/product/add-to-cart";
import ProductReviews from "@/components/product/product-reviews";
import ProductHighlights from "@/components/product/product-highlights";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchProduct(tenant: string, productId: string) {
  try {
    const res = await fetch(`${API_URL}/public/products/${productId}`, {
      headers: { "X-Tenant": tenant },
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { tenant: string; id: string };
}) {
  const product = await fetchProduct(params.tenant, params.id);
  if (!product) return { title: `Product | ${params.tenant}` };
  const title = product.meta_title || `${product.name} | ${params.tenant}`;
  const description =
    product.meta_description ||
    product.description ||
    `Buy ${product.name} from ${params.tenant}`;
  return {
    title,
    description,
    alternates: {
      canonical: `https://${params.tenant}.infalette.com/${params.tenant}/products/${product.id}`,
    },
    openGraph: {
      title,
      description,
      images: product.image_url ? [product.image_url] : undefined,
      type: "website",
    },
  };
}

function formatPrice(cents?: number | null) {
  return `₹${((cents || 0) / 100).toFixed(2)}`;
}

export default async function ProductDetailPage({
  params,
}: {
  params: { tenant: string; id: string };
}) {
  const product = await fetchProduct(params.tenant, params.id);
  if (!product) notFound();

  const price = product.sale_price_cents || product.price_cents;
  const onSale = Boolean(product.sale_price_cents);

  // Fire-and-forget funnel event (spec §3 social/website funnel:
  // Comment/DM -> Reply -> Product viewed -> Checkout -> Paid)
  void fetch(`${API_URL}/public/track`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Tenant": params.tenant },
    body: JSON.stringify({
      event_type: "product.viewed",
      product_id: product.id,
      source: "storefront",
    }),
  }).catch(() => undefined);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description || undefined,
    sku: product.sku,
    image: product.image_url ? [product.image_url] : undefined,
    brand: { "@type": "Brand", name: params.tenant },
    offers: {
      "@type": "Offer",
      priceCurrency: "INR",
      price: (price / 100).toFixed(2),
      // Stock visibility is intentionally not exposed to storefront
      // customers (sellers-only). Search engines will see offers as
      // available by default — sellers manage inventory separately.
      availability: "https://schema.org/InStock",
    },
  };

  return (
    <div className="bg-white dark:bg-black">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-10 pb-12">
        <nav className="text-[12px] text-gray-500 dark:text-neutral-500 mb-6">
          <Link href={`/${params.tenant}`} className="hover:text-gray-700 dark:hover:text-neutral-300">
            Home
          </Link>
          <span className="mx-2 opacity-60">/</span>
          <Link href={`/${params.tenant}/products`} className="hover:text-gray-700 dark:hover:text-neutral-300">
            Shop
          </Link>
          <span className="mx-2 opacity-60">/</span>
          <span className="text-gray-700 dark:text-neutral-300">{product.name}</span>
        </nav>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16">
          {/* Gallery */}
          <div className="space-y-3">
            <div className="aspect-square w-full rounded-3xl bg-gray-100 dark:bg-neutral-900 overflow-hidden">
              {product.images?.[0] || product.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={product.images?.[0] || product.image_url}
                  alt={product.name}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-gray-400">No image</div>
              )}
            </div>
            <div className="grid grid-cols-4 gap-3">
              {(product.images?.length ? product.images : product.image_url ? [product.image_url] : [])
                .slice(0, 4)
                .map((src: string, idx: number) => (
                  <div
                    key={idx}
                    className="aspect-square rounded-2xl bg-gray-100 dark:bg-neutral-900 overflow-hidden"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={src} alt={`${product.name} ${idx + 1}`} className="h-full w-full object-cover" />
                  </div>
                ))}
            </div>
          </div>

          {/* Buy box */}
          <div className="lg:sticky lg:top-20 lg:self-start">
            <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
              Infalette essentials
            </p>
            <h1 className="mt-2 text-[36px] sm:text-[44px] font-semibold leading-[1.05] tracking-tight text-gray-900 dark:text-neutral-100">
              {product.name}
            </h1>
            {product.sku && (
              <p className="mt-1 text-[12px] text-gray-400 dark:text-neutral-500">SKU · {product.sku}</p>
            )}

            <div className="mt-5 flex items-baseline gap-3">
              <span className="text-[28px] font-semibold text-gray-900 dark:text-neutral-100">
                {formatPrice(price)}
              </span>
              {onSale && (
                <span className="text-[15px] text-gray-400 line-through">
                  {formatPrice(product.price_cents)}
                </span>
              )}
            </div>

            {product.description && (
              <p className="mt-5 text-[15px] leading-relaxed text-gray-700 dark:text-neutral-300">
                {product.description}
              </p>
            )}

            <div className="mt-8">
              <AddToCart tenant={params.tenant} product={product} />
            </div>

            <div className="mt-8 space-y-2 text-[13px] text-gray-500 dark:text-neutral-400">
              <p className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                Free shipping over ₹1,000
              </p>
              <p className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-500" />
                Secure checkout · Razorpay, Stripe or COD
              </p>
              <p className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
                Easy 7-day returns
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Highlights / Specs */}
      <ProductHighlights product={product} />

      {/* Description */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 py-12 border-t border-gray-100 dark:border-neutral-900">
        <h2 className="text-[24px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Description
        </h2>
        <p className="mt-3 text-[15px] leading-relaxed text-gray-700 dark:text-neutral-300 whitespace-pre-line">
          {product.description ||
            "A carefully curated essential, handpicked for everyday use. Full ingredient and origin information is published on the product listing."}
        </p>

        {product.ingredients && (
          <div className="mt-6">
            <h3 className="text-[13px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
              Ingredients / Materials
            </h3>
            <p className="mt-2 text-[15px] text-gray-700 dark:text-neutral-300">{product.ingredients}</p>
          </div>
        )}
        {product.safety_info && (
          <div className="mt-6">
            <h3 className="text-[13px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
              Safety & warnings
            </h3>
            <p className="mt-2 text-[15px] text-gray-700 dark:text-neutral-300">{product.safety_info}</p>
          </div>
        )}
        {(product.age_suitability || product.pregnancy_stage) && (
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-6">
            {product.age_suitability && (
              <div>
                <h3 className="text-[13px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
                  Age suitability
                </h3>
                <p className="mt-2 text-[15px] text-gray-700 dark:text-neutral-300">
                  {String(product.age_suitability).replace(/_/g, " ")}
                </p>
              </div>
            )}
            {product.pregnancy_stage && (
              <div>
                <h3 className="text-[13px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
                  Stage
                </h3>
                <p className="mt-2 text-[15px] text-gray-700 dark:text-neutral-300">
                  {String(product.pregnancy_stage).replace(/_/g, " ")}
                </p>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Reviews */}
      <ProductReviews product={product} tenant={params.tenant} />
    </div>
  );
}