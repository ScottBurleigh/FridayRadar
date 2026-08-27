import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE, sessionTokenValid } from "@/lib/auth";

/**
 * Site-wide login gate.
 *
 * Next 16 renamed the `middleware` file convention to `proxy` — this must stay
 * named proxy.ts (see node_modules/next/dist/docs/.../proxy.md).
 *
 * No matcher is exported: this runs on every request, and the small allowlist
 * below is what stays reachable while signed out. Page routes are gated by
 * path, which also covers their RSC payloads (`/foo?_rsc=…`), so page data
 * can't be read around the login.
 */

/** Assets the login page itself needs before a session exists. */
function isPublicPath(pathname: string): boolean {
  if (pathname === "/login" || pathname === "/logout") return true;
  // Build output and optimized images — needed to render /login at all.
  if (pathname.startsWith("/_next/static") || pathname.startsWith("/_next/image")) return true;
  if (pathname === "/favicon.ico") return true;
  if (pathname === "/fridayradar-mark.svg" || pathname === "/fridayradar-logo.png") return true;
  return false;
}

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) return NextResponse.next();

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (await sessionTokenValid(token)) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  const destination = `${pathname}${search}`;
  if (destination && destination !== "/") {
    url.searchParams.set("next", destination);
  }
  const response = NextResponse.redirect(url);
  response.headers.set("Cache-Control", "no-store");
  return response;
}
