import { NextResponse, type NextRequest } from "next/server";

import { decide } from "@/lib/auth-guard";

// Server-side base URL for the API. Inside Docker this is the backend service
// (http://backend:8000), not the browser-facing NEXT_PUBLIC_API_URL.
const API = (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").replace(
  /\/+$/,
  "",
);

export async function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname + request.nextUrl.search;
  let status: number | "error" = "error";
  let role: string | undefined;

  try {
    const res = await fetch(`${API}/api/auth/me/`, {
      // Forward only the session cookie; nothing else from the request.
      headers: { cookie: request.headers.get("cookie") ?? "", accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    status = res.status;
    if (res.ok) role = ((await res.json()) as { role?: string }).role;
  } catch {
    status = "error";
  }

  const result = decide(status, role, path);
  if (result.kind === "allow") {
    const response = NextResponse.next();
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  }
  return NextResponse.redirect(new URL(result.to, request.url));
}

export const config = { matcher: ["/portal/:path*", "/portal"] };
