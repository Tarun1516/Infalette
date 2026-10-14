import Link from "next/link";

/**
 * Storefront footer. Matches the layout-wide Apple-style minimal chrome:
 * muted text on the page background, hairline rule on top.
 */
export default function StorefrontFooter({ tenant }: { tenant: string }) {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-gray-200 dark:border-neutral-900 bg-white dark:bg-black mt-16">
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 text-gray-900 dark:text-neutral-200">
          <div className="md:col-span-2">
            <p className="text-base font-semibold tracking-tight">Infalette</p>
            <p className="mt-2 text-sm text-gray-500 dark:text-neutral-500 max-w-md">
              Trusted products for every stage. Curated essentials with full
              ingredient lists, age suitability and manufacturer transparency.
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-gray-500 dark:text-neutral-500 mb-3">Shop</p>
            <ul className="space-y-2 text-sm">
              <li><Link href={`/${tenant}/products`} className="hover:underline">All products</Link></li>
              <li><Link href={`/${tenant}/cart`} className="hover:underline">Cart</Link></li>
              <li><Link href={`/${tenant}/orders`} className="hover:underline">Orders</Link></li>
              <li><Link href={`/${tenant}/returns`} className="hover:underline">Returns</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-gray-500 dark:text-neutral-500 mb-3">Account</p>
            <ul className="space-y-2 text-sm">
              <li><Link href={`/${tenant}/account`} className="hover:underline">Profile</Link></li>
              <li><Link href={`/${tenant}/account/consent`} className="hover:underline">Consent</Link></li>
              <li><Link href={`/${tenant}/track`} className="hover:underline">Track order</Link></li>
            </ul>
          </div>
        </div>
        <div className="mt-10 pt-6 border-t border-gray-100 dark:border-neutral-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-gray-500 dark:text-neutral-500">
          <p>© {year} Infalette. All rights reserved.</p>
          <p>Pregnancy & baby product claims require evidence. See product pages for ingredients, age suitability and manufacturer.</p>
        </div>
      </div>
    </footer>
  );
}