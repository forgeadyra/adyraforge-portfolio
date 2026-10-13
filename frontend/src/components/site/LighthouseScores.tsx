import type { Lighthouse } from "@/lib/content";

const CATEGORIES: [keyof Omit<Lighthouse, "measured_on">, string][] = [
  ["performance", "Performance"],
  ["accessibility", "Accessibility"],
  ["best_practices", "Best practices"],
  ["seo", "SEO"],
];

// Lighthouse's own bands: 90+ good, 50-89 needs work, <50 poor.
function band(score: number): string {
  if (score >= 90) return "border-gold text-gold";
  if (score >= 50) return "border-amber-300/70 text-amber-200";
  return "border-red-400/70 text-red-200";
}

export function formatMeasured(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Real Lighthouse mobile scores, as entered in the admin. */
export function LighthouseScores({
  scores,
  compact = false,
}: {
  scores: Lighthouse;
  compact?: boolean;
}) {
  return (
    <dl className={`grid grid-cols-4 ${compact ? "gap-2" : "gap-4"}`}>
      {CATEGORIES.map(([key, label]) => (
        <div key={key} className="flex flex-col items-center text-center">
          <dd
            className={`flex items-center justify-center rounded-full border-2 font-display font-bold ${band(scores[key])} ${
              compact ? "h-11 w-11 text-sm" : "h-16 w-16 text-xl"
            }`}
          >
            {scores[key]}
          </dd>
          <dt className={`mt-1.5 text-muted ${compact ? "text-[11px]" : "text-xs"}`}>{label}</dt>
        </div>
      ))}
    </dl>
  );
}
