import { OG_SIZE, ogCard } from "@/lib/og";

export const alt = "AdyraForge: we forge websites that work as hard as you do.";
export const size = OG_SIZE;
export const contentType = "image/png";

export default function Image() {
  return ogCard({
    eyebrow: "Freelance web development",
    title: "We forge websites that work as hard as you do.",
    footer: "Websites · Landing pages · Web apps",
  });
}
