import { notFound } from "next/navigation";
import Link from "next/link";
import NewsletterForm from "../../components/newsletter-form";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchTenantData(tenant: string) {
  try {
    const headers: Record<string, string> = { "X-Tenant": tenant };
    const [productsRes, storeRes, pagesRes] = await Promise.all([
      fetch(`${API_URL}/public/products`, { headers, next: { revalidate: 30 } }).then((r) => r.json()).catch(() => null),
      fetch(`${API_URL}/public/store`, { headers, next: { revalidate: 60 } }).then((r) => r.json()).catch(() => null),
      fetch(`${API_URL}/public/pages`, { headers, next: { revalidate: 30 } }).then((r) => r.json()).catch(() => null),
    ]);
    const products = Array.isArray(productsRes) ? productsRes : productsRes?.data || productsRes?.items || [];
    const store = Array.isArray(storeRes) ? storeRes[0] : storeRes?.data?.[0] || storeRes;
    const pages = Array.isArray(pagesRes) ? pagesRes : pagesRes?.data || pagesRes?.items || [];
    const homepage = pages.find((p: any) => p.is_homepage || p.slug === "home" || p.slug === "homepage") || pages[0] || null;
    return { products: products.slice(0, 8), store, pages, homepage };
  } catch {
    return { products: [], store: null, pages: [], homepage: null };
  }
}

export async function generateMetadata({ params }: { params: { tenant: string } }) {
  const { store, homepage } = await fetchTenantData(params.tenant);
  const title = homepage?.meta_title || store?.name ? `${store.name || "Infalette"} |` : `${params.tenant}`;
  const description = homepage?.meta_description || store?.description || `Shop ${params.tenant} curated pregnancy, postpartum, baby and childcare products`;
  const canonical = store?.custom_domain ? `https://${store.custom_domain}` : `https://${params.tenant}.infalette.com`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, url: canonical, type: "website" },
  };
}

export default async function TenantPage({ params }: { params: { tenant: string } }) {
  const { tenant } = params;
  if (!tenant) notFound();
  const { products, store } = await fetchTenantData(tenant);
  const themeConfig = store?.theme_config || {};
  const themeColor = themeConfig.primary_color || themeConfig.primaryColor || "#0a0a0a";
  const featuredProducts = products.slice(0, 4);

  return (
    <div className="bg-white dark:bg-black">
      {/* HERO */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-12 pb-10 sm:pt-20 sm:pb-16">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
          <div>
            <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
              Curated for mother & baby
            </p>
            <h1 className="mt-3 text-[44px] sm:text-[60px] font-semibold tracking-tight leading-[1.02] text-gray-900 dark:text-neutral-100">
              Trusted products
              <br />
              for every stage.
            </h1>
            <p className="mt-5 text-[17px] leading-relaxed text-gray-700 dark:text-neutral-300 max-w-md">
              Pregnancy, postpartum, baby and childcare essentials — handpicked by {store?.name || "Infalette"}.
            </p>
            <div className="mt-8 flex gap-3">
              <Link
                href={`/${tenant}/products`}
                className="inline-flex h-12 px-7 items-center justify-center rounded-full text-[15px] font-medium text-white"
                style={{ backgroundColor: themeColor }}
              >
                Shop now
              </Link>
              <Link
                href={`/${tenant}/products`}
                className="inline-flex h-12 px-7 items-center justify-center rounded-full text-[15px] font-medium border border-gray-300 dark:border-neutral-800 text-gray-900 dark:text-neutral-100"
              >
                View collections
              </Link>
            </div>
          </div>
          <div className="aspect-[4/5] rounded-3xl overflow-hidden bg-gray-100 dark:bg-neutral-900">
            {featuredProducts[0]?.images?.[0] || featuredProducts[0]?.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={featuredProducts[0].images?.[0] || featuredProducts[0].image_url}
                alt={featuredProducts[0]?.name || "Hero"}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-gray-400 text-sm">
                Hero • Add products to display
              </div>
            )}
          </div>
        </div>
      </section>

      {/* FEATURED PRODUCTS */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-8">
            <div>
              <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
                Bestsellers
              </p>
              <h2 className="mt-2 text-[32px] sm:text-[40px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
                Featured.
              </h2>
            </div>
            <Link
              href={`/${tenant}/products`}
              className="text-[14px] text-blue-600 dark:text-blue-400 hover:underline"
            >
              View all →
            </Link>
          </div>
          {products.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-16 px-6 text-center">
              <p className="text-gray-500 dark:text-neutral-400">No products yet</p>
              <p className="text-xs text-gray-400 dark:text-neutral-500 mt-1">
                Products added in admin will appear here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              {featuredProducts.map((p: any) => (
                <Link
                  key={p.id}
                  href={`/${tenant}/products/${p.id}`}
                  className="group block rounded-2xl bg-white dark:bg-neutral-950 hover:shadow-[0_8px_30px_rgba(0,0,0,0.08)] dark:hover:shadow-[0_8px_30px_rgba(255,255,255,0.04)] transition-all"
                >
                  <div className="aspect-square w-full overflow-hidden rounded-t-2xl bg-gray-100 dark:bg-neutral-900">
                    {p.image_url || p.images?.[0] ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={p.image_url || p.images[0]} alt={p.name} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-gray-400">
                        No image
                      </div>
                    )}
                  </div>
                  <div className="px-4 pt-3 pb-5">
                    <p className="text-[15px] font-medium text-gray-900 dark:text-neutral-100 line-clamp-1">
                      {p.name}
                    </p>
                    <p className="mt-2 text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
                      ₹{((p.sale_price_cents ?? p.price_cents) / 100).toFixed(2)}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
      </section>

      {/* VALUE PROPS */}
      <section className="bg-gray-50 dark:bg-neutral-950 border-y border-gray-100 dark:border-neutral-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
          <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
            Why Infalette
          </p>
          <h2 className="mt-2 text-[32px] sm:text-[40px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
            Made for parents.
          </h2>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-10">
            <div>
              <p className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
                Full transparency.
              </p>
              <p className="mt-2 text-[14px] text-gray-600 dark:text-neutral-400 leading-relaxed">
                Ingredients, age suitability, manufacturer and warnings on every product. No fine print.
              </p>
            </div>
            <div>
              <p className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
                Secure checkout.
              </p>
              <p className="mt-2 text-[14px] text-gray-600 dark:text-neutral-400 leading-relaxed">
                Razorpay, Stripe and Cash on Delivery. Signed webhooks prevent duplicate charges.
              </p>
            </div>
            <div>
              <p className="text-[15px] font-semibold text-gray-900 dark:text-neutral-100">
                Track everything.
              </p>
              <p className="mt-2 text-[14px] text-gray-600 dark:text-neutral-400 leading-relaxed">
                Real-time shipment tracking, downloadable GST invoices and easy returns.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* NEWSLETTER */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 py-16 text-center">
        <h2 className="text-[32px] sm:text-[40px] font-semibold tracking-tight text-gray-900 dark:text-neutral-100">
          Join the community.
        </h2>
        <p className="mt-3 text-[15px] text-gray-500 dark:text-neutral-400">
          New arrivals, restocks and curated picks delivered to your inbox. No spam.
        </p>
        <div className="mt-8">
          <NewsletterForm storeId={store?.id} themeColor={themeColor} />
        </div>
      </section>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({ "@context": "https://schema.org", "@type": "Store", name: store?.name || "Infalette", url: `https://${store?.custom_domain || `${tenant}.infalette.com`}` }) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({ "@context":"https://schema.org", "@type":"BreadcrumbList", itemListElement:[{ "@type":"ListItem", position:1, name:"Home", item:`https://${tenant}.infalette.com/${tenant}` }] }) }} />
    </div>
  );
}