import { NextResponse, type NextRequest } from "next/server";
import { IDENTITY_SERVICE_BASE_URL, REFRESH_TOKEN_COOKIE } from "@/lib/server/backend-config";
import { apiFetch } from "@/lib/api/http-client";

/**
 * Idempotent, mirrors identity-service's own /api/v1/auth/logout contract
 * -- clears the cookie regardless of whether the upstream call succeeds (a
 * stale/already-revoked refresh token must not leave the browser holding
 * onto a cookie it can never use again). Reads via `request.cookies` --
 * see app/api/auth/refresh/route.ts's header comment for why, over
 * `next/headers`'s `cookies()`.
 */
export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
  if (refreshToken) {
    try {
      await apiFetch(`${IDENTITY_SERVICE_BASE_URL}/api/v1/auth/logout`, {
        method: "POST",
        body: { refresh_token: refreshToken },
      });
    } catch {
      // Best-effort revoke -- still clear the cookie below regardless.
    }
  }
  const response = NextResponse.json({ revoked: true });
  response.cookies.delete(REFRESH_TOKEN_COOKIE);
  return response;
}
