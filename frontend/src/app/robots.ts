import type { MetadataRoute } from "next";

import { site } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Private or token-bearing areas: never indexed.
      disallow: ["/portal", "/login", "/invite/", "/reset-password/", "/forgot-password"],
    },
    sitemap: `${site.url}/sitemap.xml`,
    host: site.url,
  };
}
