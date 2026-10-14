import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

/**
 * Edge middleware: maps custom domains and subdomains to tenants.
 *
 * - Requests arriving on a custom domain (no /[tenant] path prefix) are
 *   resolved via the public /resolve endpoint and internally rewritten to
 *   the tenant's path-scoped pages.
 * - Tenant-configured SEO redirects (301/302) are honored at the edge.
 *
 * Path-prefixed URLs (/{tenant}/...) pass through untouched.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// Hosts that never map to a tenant (local dev, platform surfaces).
const RESERVED_HOSTS = new Set([
  "localhost",
  "127.0.0.1",
  "0.0.0.0",
]);

// Cache resolutions briefly to keep the edge fast (per lambda instance).
const resolveCache = new Map<
  string,
  { tenant: string; redirects: { old_path: string; new_path: string; status_code: number }[]; ts: number }
>();
const CACHE_TTL_MS = 60_000;

type ResolveResult = {
  tenant: string;
  redirects: { old_path: string; new_path: string; status_code: number }[];
};

async function resolveHost(host: string): Promise<ResolveResult | null> {
  const cached = resolveCache.get(host);
  if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
    return { tenant: cached.tenant, redirects: cached.redirects };
  }
  try {
    const res = await fetch(`${API_URL}/public/resolve?host=${encodeURIComponent(host)}`, {
      headers: { accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data?.tenant) return null;
    const entry = {
      tenant: data.tenant as string,
      redirects: (data.redirects || []) as ResolveResult["redirects"],
      ts: Date.now(),
    };
    resolveCache.set(host, entry);
    return { tenant: entry.tenant, redirects: entry.redirects };
  } catch {
    return null;
  }
}

export const middleware = clerkMiddleware(async (auth, request: NextRequest) => {
  const host = (request.headers.get("host") || "").split(":")[0].toLowerCase();
  const pathname = request.nextUrl.pathname;

  // Skip tenant mapping for static/API/Clerk internals — Clerk auth still runs.
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/__clerk/") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  // Local/dev hosts use the /[tenant] path convention — no mapping.
  if (RESERVED_HOSTS.has(host)) {
    return NextResponse.next();
  }

  const resolved = await resolveHost(host);
  if (!resolved) {
    return NextResponse.next();
  }

  const firstSegment = pathname.split("/")[1] || "";
  const tenantScoped = firstSegment === resolved.tenant;
  // Path relative to the tenant root as the shopper sees it.
  const rootPath = tenantScoped
    ? pathname.slice(resolved.tenant.length + 1) || "/"
    : pathname;

  // 1. Tenant redirects take priority for exact old_path matches.
  const match = resolved.redirects.find((r) => r.old_path === rootPath);
  if (match) {
    const url = request.nextUrl.clone();
    url.pathname = match.new_path.startsWith("/") ? match.new_path : `/${match.new_path}`;
    return NextResponse.redirect(url, match.status_code as 301 | 302 | 308);
  }

  if (tenantScoped) {
    // Tenant content requested by absolute path on a custom domain:
    // strip the prefix so the page renders at the domain root.
    const url = request.nextUrl.clone();
    url.pathname = rootPath;
    const res = NextResponse.rewrite(url);
    res.headers.set("x-rewrote-tenant", resolved.tenant);
    return res;
  }

  // 2. Bare paths on a custom domain → rewrite into the tenant's scope.
  const url = request.nextUrl.clone();
  url.pathname = `/${resolved.tenant}${pathname === "/" ? "" : pathname}`;
  const res = NextResponse.rewrite(url);
  res.headers.set("x-rewrote-tenant", resolved.tenant);
  return res;
});

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
    "/(api|trpc)(.*)",
    "/__clerk/:path*",
  ],
};
