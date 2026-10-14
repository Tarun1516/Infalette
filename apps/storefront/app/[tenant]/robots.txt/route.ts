import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest, { params }: { params: { tenant: string } }) {
  const host = req.headers.get("host") || `${params.tenant}.infalette.com`;
  const protocol = req.headers.get("x-forwarded-proto") || "https";
  const base = `${protocol}://${host}`;

  const body = `User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Sitemap: ${base}/${params.tenant}/sitemap.xml
`;
  return new NextResponse(body, { headers: { "Content-Type": "text/plain" } });
}
