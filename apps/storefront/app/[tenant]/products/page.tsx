import Link from "next/link";
import ProductCard from "@/components/product/product-card";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchProducts(tenant: string) {
  try {
    const res = await fetch(`${API_URL}/public/products`, {
      headers: { "X-Tenant": tenant },
      next: { revalidate: 30 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.data || [];
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: { tenant: string };
}) {
  return {
    title: `Shop | ${params.tenant}`,
    description: `Browse pregnancy, postpartum, baby and childcare products from ${params.tenant}`,
    alternates: { canonical: `https://${params.tenant}.infalette.com/${params.tenant}/products` },
  };
}

export default async function ProductsPage({
  params,
}: {
  params: { tenant: string };
}) {
  const products = await fetchProducts(params.tenant);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
      <header className="mb-10">
        <p className="text-[12px] uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500">
          Storefront
        </p>
        <h1 className="mt-2 text-[40px] sm:text-[52px] font-semibold leading-[1.05] tracking-tight text-gray-900 dark:text-neutral-100">
          Shop everything.
        </h1>
        <p className="mt-3 text-[15px] text-gray-500 dark:text-neutral-400 max-w-2xl">
          Curated essentials for pregnancy, postpartum, baby and childcare.
          Every product lists its full ingredients, age suitability and
          manufacturer so you can buy with confidence.
        </p>
      </header>

      {products.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 dark:border-neutral-800 py-20 px-6 text-center">
          <p className="text-gray-500 dark:text-neutral-400">No products available yet.</p>
          <p className="mt-1 text-xs text-gray-400 dark:text-neutral-500">
            Check back shortly — new arrivals are added every week.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {products.map((p: any) => (
            <ProductCard key={p.id} product={p} tenant={params.tenant} />
          ))}
        </div>
      )}
    </div>
  );
}