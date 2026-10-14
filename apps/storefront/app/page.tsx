import { redirect } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Root page.
 *
 * The storefront is a multi-tenant app that lives under /[tenant]. When a
 * visitor hits `/`, we try to be helpful:
 *   - Query the public tenants endpoint.
 *   - If exactly one tenant exists, redirect straight to it.
 *   - If many exist, show a small directory.
 *   - If none exist (fresh DB), show a hint about seeding the demo data.
 */
export const dynamic = "force-dynamic";

type Tenant = { slug: string; name: string };

async function fetchTenants(): Promise<Tenant[]> {
  // Prefer a dedicated /public/tenants endpoint if the API exposes it.
  // Fall back to scraping the public/store endpoint by host if needed.
  const endpoints = [
    `${API_URL}/public/tenants`,
    `${API_URL}/public/store`,
  ];
  for (const url of endpoints) {
    try {
      const res = await fetch(url, {
        cache: "no-store",
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) continue;
      const data = await res.json();
      const list = Array.isArray(data) ? data : data?.data || data?.items || [];
      if (!Array.isArray(list) || list.length === 0) continue;
      return list
        .filter((t: any) => t && (t.slug || t.tenant_slug))
        .map((t: any) => ({
          slug: t.slug || t.tenant_slug,
          name: t.name || t.tenant_name || t.slug || t.tenant_slug,
        }));
    } catch {
      // try the next endpoint
    }
  }
  return [];
}

export default async function RootPage() {
  let tenants = await fetchTenants();

  // Last-ditch: fall back to the canonical demo tenant if we know the
  // environment has one. This keeps the local dev story smooth.
  if (tenants.length === 0 && process.env.NEXT_PUBLIC_DEMO_TENANT) {
    tenants = [
      {
        slug: process.env.NEXT_PUBLIC_DEMO_TENANT,
        name: process.env.NEXT_PUBLIC_DEMO_TENANT,
      },
    ];
  }

  if (tenants.length === 1) {
    redirect(`/${tenants[0].slug}`);
  }

  return (
    <main className="min-h-screen flex items-center justify-center font-sans bg-gray-50 p-8">
      <div className="max-w-xl text-center">
        <h1 className="text-2xl font-semibold mb-2 text-gray-900">
          Infalette Storefront
        </h1>
        <p className="text-gray-600 mb-6">
          {tenants.length === 0
            ? "No tenants found. Seed the demo data with: pnpm db:seed"
            : "Pick a store to visit:"}
        </p>
        {tenants.length > 0 && (
          <ul className="list-none p-0 m-0 space-y-2">
            {tenants.map((t) => (
              <li key={t.slug}>
                <a
                  href={`/${t.slug}`}
                  className="inline-block px-5 py-2.5 bg-gray-900 text-white rounded-md no-underline hover:bg-gray-700 transition-colors"
                >
                  {t.name}{" "}
                  <span className="opacity-60">/{t.slug}</span>
                </a>
              </li>
            ))}
          </ul>
        )}
        {tenants.length === 0 && (
          <code className="block px-3 py-2 bg-gray-100 rounded text-sm font-mono">
            python scripts/demo_seed.py
          </code>
        )}
      </div>
    </main>
  );
}
