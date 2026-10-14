import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_STOREFRONT_URL || "https://infalette.com";
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/admin/", "/_next/"] },
    sitemap: `${base}/sitemap.xml`,
  };
}
