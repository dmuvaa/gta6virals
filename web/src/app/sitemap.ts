import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const pages: [string, number, "weekly" | "monthly" | "yearly"][] = [
    ["/", 1, "weekly"], ["/pricing", 0.8, "monthly"], ["/faq", 0.6, "monthly"], ["/signup", 0.5, "yearly"],
    ["/legal/terms", 0.2, "yearly"], ["/legal/privacy", 0.2, "yearly"], ["/legal/refunds", 0.2, "yearly"], ["/legal/copyright", 0.2, "yearly"],
  ];
  return pages.map(([p, priority, changeFrequency]) => ({ url: `${SITE_URL}${p}`, lastModified: now, changeFrequency, priority }));
}
