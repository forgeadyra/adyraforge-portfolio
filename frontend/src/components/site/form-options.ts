/** Choice values mirror backend/apps/leads/models.py exactly. */

export const PROJECT_TYPES = [
  ["landing_page", "Landing page"],
  ["business_website", "Business website"],
  ["web_app", "Web application"],
  ["ecommerce", "E-commerce"],
  ["redesign", "Redesign"],
  ["other", "Other"],
] as const;

export const BUDGETS = [
  ["not_sure", "Not sure yet"],
  ["under_500", "Under $500 / ₹40k"],
  ["500_1500", "$500–1,500 / ₹40k–1.25L"],
  ["1500_5000", "$1,500–5,000 / ₹1.25L–4L"],
  ["5000_plus", "$5,000+ / ₹4L+"],
] as const;

export const TIMELINES = [
  ["flexible", "Flexible"],
  ["asap", "As soon as possible"],
  ["1_month", "Within a month"],
  ["1_3_months", "1–3 months"],
] as const;

export const FEATURES = [
  "Contact form",
  "Online booking",
  "Online payments",
  "Client login / portal",
  "Blog or news",
  "Content you can edit yourself",
  "Multiple languages",
  "Admin dashboard",
  "Analytics",
] as const;

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"] as const;

/** UTM attribution from the landing URL, trimmed to the backend's limits. */
export function utmFromUrl(): Partial<Record<(typeof UTM_KEYS)[number], string>> {
  const params = new URLSearchParams(window.location.search);
  const out: Partial<Record<(typeof UTM_KEYS)[number], string>> = {};
  for (const key of UTM_KEYS) {
    const value = params.get(key);
    if (value) out[key] = value.slice(0, 100);
  }
  return out;
}
