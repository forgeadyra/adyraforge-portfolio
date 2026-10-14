/**
 * Server-side content client for the public site (ISR, revalidate 1h).
 *
 * On an API error this throws, so a failed background revalidation keeps
 * serving the last good page instead of caching an empty one, and a production
 * build fails instead of shipping an empty site: an unreachable API, a 404 from a
 * list endpoint (wrong URL, service not deployed) and an empty project list all
 * abort `next build`. CI builds without a backend set NEXT_BUILD_WITHOUT_API=1 to
 * render empty states; Netlify never sets it.
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

export interface Lighthouse {
  performance: number;
  accessibility: number;
  best_practices: number;
  seo: number;
  measured_on: string;
}

export interface ProjectCard {
  slug: string;
  title: string;
  summary: string;
  industry: string;
  /** client = paid client work; concept = self-initiated, never shown as a client. */
  kind: "client" | "concept";
  status: "live" | "not_live";
  is_featured: boolean;
  live_url: string;
  cover_image: string | null;
  cover_alt: string;
  technologies: Technology[];
  services: ServiceRef[];
  /** Real Lighthouse mobile scores; null unless all four are entered. */
  lighthouse: Lighthouse | null;
  updated_at: string;
}

export interface ProjectDetail extends ProjectCard {
  client_name: string;
  problem: string;
  solution: string;
  result_metrics: { label: string; value: string }[];
  results_note: string;
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

// `next build` sets NEXT_PHASE; runtime ISR revalidation does not.
const BUILDING = process.env.NEXT_PHASE === "phase-production-build";

/**
 * `notFound` is returned for a 404 only where a 404 is a real answer (one project
 * by slug). A list endpoint answering 404 means a wrong URL or an API that isn't
 * deployed, so it throws like any other failure.
 */
async function get<T>(path: string, fallback: T, notFound?: T): Promise<T> {
  if (OFFLINE) return fallback;
  const res = await fetch(`${API}/api/public/${path}`, {
    headers: { accept: "application/json" },
    next: { revalidate: REVALIDATE_SECONDS, tags: ["content"] },
  });
  if (res.status === 404 && notFound !== undefined) return notFound;
  if (!res.ok) throw new Error(`Content API returned ${res.status} for ${path}`);
  return (await res.json()) as T;
}

async function allProjects(query: string): Promise<ProjectCard[]> {
  const projects = await get<ProjectCard[]>(`projects/${query}`, []);
  if (BUILDING && !OFFLINE && query === "" && projects.length === 0) {
    throw new Error(
      `Refusing to ship an empty site: ${API}/api/public/projects/ returned no published projects.`,
    );
  }
  return projects;
}

export const content = {
  projects: (query = "") => allProjects(query),
  project: (slug: string) =>
    get<ProjectDetail | null>(`projects/${encodeURIComponent(slug)}/`, null, null),
  services: () => get<Service[]>("services/", []),
  technologies: () => get<Technology[]>("technologies/", []),
  testimonials: () => get<Testimonial[]>("testimonials/", []),
};
