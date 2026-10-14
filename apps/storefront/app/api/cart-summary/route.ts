import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/cart-summary?tenant=demo-store
 *
 * Proxies the public cart endpoint to compute a compact summary
 * (item count + total) the storefront header can use to render a live
 * cart badge. Forwards the cart session id cookie/header so guest
 * carts work the same as on the cart page.
 */
export const dynamic = "force-dynamic";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function GET(req: NextRequest) {
  const tenant = req.nextUrl.searchParams.get("tenant") || "";
  if (!tenant) {
    return NextResponse.json({ count: 0, totalCents: 0 });
  }
  const sessionKey =
    req.cookies.get("infalette-cart-session")?.value ||
    req.headers.get("x-cart-session-id") ||
    "";

  const headers: Record<string, string> = { "X-Tenant": tenant };
  if (sessionKey) headers["X-Cart-Session-ID"] = sessionKey;

  try {
    const res = await fetch(`${API_URL}/cart/`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ count: 0, totalCents: 0 });
    }
    const data = await res.json();
    const items: any[] = data?.items || [];
    const count = items.reduce((sum: number, it: any) => sum + (it.quantity || 1), 0);
    const totalCents =
      data?.total_cents ??
      items.reduce(
        (sum: number, it: any) => sum + (it.price_cents ?? 0) * (it.quantity ?? 1),
        0,
      );
    return NextResponse.json({ count, totalCents });
  } catch {
    return NextResponse.json({ count: 0, totalCents: 0 });
  }
}