import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function GET(req: NextRequest, { params }: { params: { tenant: string } }) {
  const tenant = params.tenant;
  const host = req.headers.get("host") || `${tenant}.infalette.com`;
  const protocol = req.headers.get("x-forwarded-proto") || "https";
  const baseUrl = `${protocol}://${host}`;

  try {
    // Try to fetch SEO sitemap from API
    const res = await fetch(`${API_URL}/seo/sitemap?tenant=${tenant}`, {
      headers: { "X-Tenant": tenant },
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const xml = await res.text();
      // Ensure baseUrl is correct
      return new NextResponse(xml, { headers: { "Content-Type": "application/xml" } });
    }
  } catch {}

  // Fallback: generate minimal sitemap from products
  let products: any[] = [];
  try {
    const r = await fetch(`${API_URL}/public/products`, {
      headers: { "X-Tenant": tenant },
      next: { revalidate: 3600 },
    });
    const data = await r.json();
    products = Array.isArray(data) ? data : data.data || data.items || [];
  } catch {}

  const urls = [
    `<url><loc>${baseUrl}/${tenant}</loc><changefreq>daily</changefreq><priority>1.0</priority></url>`,
    `<url><loc>${baseUrl}/${tenant}/products</loc><changefreq>daily</changefreq><priority>0.8</priority></url>`,
    ...products.map(
      (p: any) => `<url><loc>${baseUrl}/${tenant}/products/${p.id}</loc><lastmod>${p.updated_at ? new Date(p.updated_at).toISOString() : new Date().toISOString()}</lastmod><priority>0.6</priority></url>`
    ),
  ].join("");

  const xml = `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`;
  return new NextResponse(xml, { headers: { "Content-Type": "application/xml" } });
}
