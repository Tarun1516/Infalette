import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_STOREFRONT_URL || "https://infalette.com";
  return [
    { url: base, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    { url: `${base}/tenants`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.5 },
  ];
}
