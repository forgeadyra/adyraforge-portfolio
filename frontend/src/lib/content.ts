/**
 * Server-side content client for the public site (ISR, revalidate 1h).
 *
 * On an API error this throws, so a failed background revalidation keeps
 * serving the last good page instead of caching an empty one. CI builds
 * without a backend set NEXT_BUILD_WITHOUT_API=1 to render empty states.
 */

export const REVALIDATE_SECONDS = 3600;

const API = (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").replace(
  /\/+$/,
  "",
);
const OFFLINE = process.env.NEXT_BUILD_WITHOUT_API === "1";

export interface Technology {
  name: string;
  slug: string;
  category: string;
}

export interface ServiceRef {
  name: string;
  slug: string;
}

export interface Service extends ServiceRef {
  summary: string;
  description: string;
  includes: string[];
  price_from_inr: number | null;
  price_from_usd: number | null;
}

export interface ProjectCard {
  slug: string;
  title: string;
  summary: string;
  industry: string;
  status: "live" | "concept";
  is_featured: boolean;
  live_url: string;
  cover_image: string | null;
  cover_alt: string;
  technologies: Technology[];
  services: ServiceRef[];
  updated_at: string;
}

export interface ProjectDetail extends ProjectCard {
  client_name: string;
  problem: string;
  solution: string;
  result_metrics: { label: string; value: string }[];
  repo_url: string;
  gallery: { image: string | null; alt_text: string; caption: string }[];
  similar: ProjectCard[];
  created_at: string;
}

export interface Testimonial {
  author_name: string;
  author_role: string;
  company: string;
  quote: string;
  rating: number | null;
  project: string | null;
  avatar: string | null;
}

export interface Stats {
  live_projects: number;
  industries: string[];
  response_time_hours: number | null;
}

async function get<T>(path: string, fallback: T): Promise<T> {
  if (OFFLINE) return fallback;
  const res = await fetch(`${API}/api/public/${path}`, {
    headers: { accept: "application/json" },
    next: { revalidate: REVALIDATE_SECONDS, tags: ["content"] },
  });
  if (res.status === 404) return fallback;
  if (!res.ok) throw new Error(`Content API returned ${res.status} for ${path}`);
  return (await res.json()) as T;
}

export const content = {
  projects: (query = "") => get<ProjectCard[]>(`projects/${query}`, []),
  featured: () => get<ProjectCard[]>("projects/?featured=1", []),
  project: (slug: string) =>
    get<ProjectDetail | null>(`projects/${encodeURIComponent(slug)}/`, null),
  services: () => get<Service[]>("services/", []),
  technologies: () => get<Technology[]>("technologies/", []),
  testimonials: () => get<Testimonial[]>("testimonials/", []),
  stats: () =>
    get<Stats>("stats/", { live_projects: 0, industries: [], response_time_hours: null }),
};
