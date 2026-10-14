/**
 * Typed client for the Django API.
 *
 * - Session auth: every request sends cookies (`credentials: "include"`).
 *   Nothing auth-related is ever stored in localStorage.
 * - CSRF: the token comes from GET /api/auth/csrf/ (JSON body), is kept in
 *   memory only, and is sent as X-CSRFToken on unsafe methods. Call
 *   `resetCsrfToken()` after login/logout, because Django rotates it.
 */

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly data: unknown,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  signal?: AbortSignal;
}

interface ClientConfig {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

const SAFE_METHODS = new Set<HttpMethod>(["GET"]);

function detailOf(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const { detail } = data as { detail: unknown };
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export function createApiClient({ baseUrl, fetchImpl }: ClientConfig) {
  const base = baseUrl.replace(/\/+$/, "");
  // Resolve lazily so tests (and polyfills) can swap the global.
  const doFetch: typeof fetch = (...args) => (fetchImpl ?? fetch)(...args);
  let csrfToken: string | null = null;
  let pendingToken: Promise<string> | null = null;

  function urlFor(path: string): string {
    // Only relative API paths: credentials must never be sent to another origin.
    if (!path.startsWith("/") || path.startsWith("//")) {
      throw new Error(`API paths must be relative and start with "/": ${path}`);
    }
    return `${base}${path}`;
  }

  async function getCsrfToken(): Promise<string> {
    if (csrfToken) return csrfToken;
    pendingToken ??= (async () => {
      const res = await doFetch(urlFor("/api/auth/csrf/"), {
        credentials: "include",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!res.ok) throw new ApiError(res.status, "Could not obtain CSRF token.", null);
      const data = (await res.json()) as { csrfToken: string };
      csrfToken = data.csrfToken;
      return csrfToken;
    })().finally(() => {
      pendingToken = null;
    });
    return pendingToken;
  }

  function resetCsrfToken(): void {
    csrfToken = null;
  }

  async function request<T>(
    path: string,
    options: RequestOptions = {},
    retried = false,
  ): Promise<T> {
    const method = options.method ?? "GET";
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (!SAFE_METHODS.has(method)) headers["X-CSRFToken"] = await getCsrfToken();

    const res = await doFetch(urlFor(path), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "include",
      cache: "no-store",
      signal: options.signal,
    });

    if (res.status === 204) return undefined as T;

    const data: unknown = res.headers.get("content-type")?.includes("application/json")
      ? await res.json()
      : null;

    if (!res.ok) {
      const detail = detailOf(data, res.statusText || "Request failed.");
      // A stale token (e.g. rotated at login) gets one transparent retry.
      if (res.status === 403 && !retried && !SAFE_METHODS.has(method) && /csrf/i.test(detail)) {
        resetCsrfToken();
        return request<T>(path, options, true);
      }
      throw new ApiError(res.status, detail, data);
    }
    return data as T;
  }

  return {
    get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
    post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
    put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
    delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
    getCsrfToken,
    resetCsrfToken,
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

// Same-origin: the browser only ever talks to the site's own host, which proxies
// /api/* to Django (Netlify in production). Cookies stay first-party.
export const api = createApiClient({ baseUrl: "" });

// --- Endpoint types -----------------------------------------------------------

export interface Me {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "client";
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Milestone {
  id: number;
  title: string;
  description: string;
  due_date: string | null;
  completed_at: string | null;
  is_complete: boolean;
  order: number;
}

export type ProjectStatus =
  "planning" | "in_progress" | "review" | "completed" | "on_hold" | "cancelled";

export interface ProjectSummary {
  id: number;
  title: string;
  status: ProjectStatus;
  progress: number;
  start_date: string | null;
  due_date: string | null;
  updated_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  description: string;
  milestones: Milestone[];
  created_at: string;
}

export interface Message {
  id: number;
  client_project: number;
  body: string;
  sender_name: string;
  is_mine: boolean;
  read_at: string | null;
  created_at: string;
}

export interface ProjectFile {
  id: number;
  client_project: number;
  original_name: string;
  description: string;
  content_type: string;
  size: number;
  created_at: string;
}

export interface Invoice {
  id: number;
  client_project: number;
  number: string;
  amount: string;
  currency: "INR" | "USD";
  status: "sent" | "paid" | "overdue" | "void";
  issued_on: string | null;
  due_date: string;
  paid_at: string | null;
  has_pdf: boolean;
}

export interface DownloadLink {
  url: string;
  expires_in: number;
}

export interface LoginBody {
  email: string;
  password: string;
  otp_token?: string;
}

const byProject = (project?: number) => (project ? `?project=${project}` : "");

export const endpoints = {
  me: (signal?: AbortSignal) => api.get<Me>("/api/auth/me/", signal),

  async login(body: LoginBody): Promise<Me> {
    const me = await api.post<Me>("/api/auth/login/", body);
    api.resetCsrfToken(); // Django rotates the CSRF token on login
    return me;
  },
  async logout(): Promise<void> {
    await api.post("/api/auth/logout/");
    api.resetCsrfToken();
  },
  async logoutAll(): Promise<void> {
    await api.post("/api/auth/logout-all/");
    api.resetCsrfToken();
  },
  changePassword: (current_password: string, new_password: string) =>
    api.post<{ detail: string }>("/api/auth/password/change/", { current_password, new_password }),
  requestPasswordReset: (email: string) =>
    api.post<{ detail: string }>("/api/auth/password/reset/", { email }),
  confirmPasswordReset: (uid: string, token: string, new_password: string) =>
    api.post<{ detail: string }>("/api/auth/password/reset/confirm/", { uid, token, new_password }),
  acceptInvite: (token: string, new_password: string) =>
    api.post<{ detail: string }>("/api/auth/invite/accept/", { token, new_password }),

  projects: () => api.get<Page<ProjectSummary>>("/api/portal/projects/"),
  project: (id: number) => api.get<ProjectDetail>(`/api/portal/projects/${id}/`),
  messages: (projectId: number) =>
    api.get<Page<Message>>(`/api/portal/projects/${projectId}/messages/`),
  sendMessage: (projectId: number, body: string) =>
    api.post<Message>(`/api/portal/projects/${projectId}/messages/`, { body }),
  markRead: (messageId: number) =>
    api.patch<Message>(`/api/portal/messages/${messageId}/`, { read: true }),
  files: (project?: number) =>
    api.get<Page<ProjectFile>>(`/api/portal/files/${byProject(project)}`),
  fileDownload: (id: number) => api.get<DownloadLink>(`/api/portal/files/${id}/download/`),
  invoices: (project?: number) =>
    api.get<Page<Invoice>>(`/api/portal/invoices/${byProject(project)}`),
  invoiceDownload: (id: number) => api.get<DownloadLink>(`/api/portal/invoices/${id}/download/`),
};
