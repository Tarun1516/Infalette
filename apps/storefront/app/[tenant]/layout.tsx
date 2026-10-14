import StorefrontHeader from "../../components/storefront-header";
import StorefrontFooter from "../../components/storefront-footer";

/**
 * Shared chrome for every page inside a tenant storefront.
 *
 * The tenant header (logo, primary nav, theme toggle, optional back
 * button) sits above the page content. The footer sits below.
 *
 * The header component itself hides the back button on the home route
 * (`/${tenant}`); all other sub-pages (cart, products, account, …)
 * show it.
 */
export default function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { tenant: string };
}) {
  return (
    <div className="min-h-screen flex flex-col bg-white text-gray-900 dark:bg-black dark:text-gray-100">
      <StorefrontHeader tenant={params.tenant} />
      <main className="flex-1">{children}</main>
      <StorefrontFooter tenant={params.tenant} />
    </div>
  );
}