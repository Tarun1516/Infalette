import { redirect } from "next/navigation";

/**
 * Root page for the admin app.
 *
 * The admin lives at specific sub-paths (dashboard, products, orders, ...).
 * When a visitor hits `/` we send them to the login page if they aren't
 * authenticated, and to the dashboard if they are.
 */
export default function AdminRootPage() {
  // We don't have access to the auth cookie from a server component
  // without a fetch round-trip, so just send everyone to the login
  // screen — the auth guard will bounce authenticated users to the
  // dashboard.
  redirect("/login");
}
