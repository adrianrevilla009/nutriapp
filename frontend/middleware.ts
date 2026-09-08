import { NextResponse, type NextRequest } from "next/server";
import { REFRESH_TOKEN_COOKIE } from "@/lib/server/backend-config";

const PROTECTED_PATHS = ["/search", "/log", "/dashboard"];
const PUBLIC_ONLY_PATHS = ["/login", "/register"];

/**
 * Route protection (implementation plan section 1 / test-plan section 3).
 * Checks only for the PRESENCE of the httpOnly refresh-token cookie -- it
 * cannot verify the cookie is still valid (that's identity-service's job,
 * checked on the next actual API call via useSession's silent refresh).
 * This is a UX redirect, not the security boundary: every real
 * authorization decision still happens server-side per
 * docs/authorization-model.md section 3 ("fine-grained authorization is
 * always enforced in the owning domain service").
 */
export function middleware(request: NextRequest) {
  const hasSessionCookie = request.cookies.has(REFRESH_TOKEN_COOKIE);
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (isProtected && !hasSessionCookie) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  const isPublicOnly = PUBLIC_ONLY_PATHS.some((p) => pathname === p);
  if (isPublicOnly && hasSessionCookie) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/search/:path*", "/log/:path*", "/dashboard/:path*", "/login", "/register"],
};
