import type { MetadataRoute } from "next";

import { content } from "@/lib/content";
import { site } from "@/lib/site";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const projects = await content.projects();
  const pages = ["", "/work", "/services", "/planner", "/about", "/contact"].map((path) => ({
    url: `${site.url}${path}`,
    changeFrequency: "monthly" as const,
    priority: path === "" ? 1 : 0.7,
  }));
  return [
    ...pages,
    ...projects.map((p) => ({
      url: `${site.url}/work/${p.slug}`,
      lastModified: p.updated_at,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
