import { content } from "@/lib/content";
import { OG_SIZE, ogCard } from "@/lib/og";

export const alt = "AdyraForge case study";
export const size = OG_SIZE;
export const contentType = "image/png";
export const revalidate = 3600;

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const project = await content.project((await params).slug);
  return ogCard({
    eyebrow: project
      ? `Case study · ${project.status === "live" ? "Live" : "Concept"}`
      : "Case study",
    title: project?.title ?? "AdyraForge",
    footer: project?.industry || "Web project",
  });
}
