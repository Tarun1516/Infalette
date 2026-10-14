import { redirect } from "next/navigation";

/**
 * Root page for the platform-admin app.
 *
 * Sends every visitor at `/` to the dashboard, which is the canonical
 * landing surface once the user is authenticated.
 */
export default function PlatformAdminRootPage() {
  redirect("/dashboard");
}
