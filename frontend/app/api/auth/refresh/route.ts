import { NextResponse, type NextRequest } from "next/server";
import { IDENTITY_SERVICE_BASE_URL, REFRESH_TOKEN_COOKIE } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

/**
 * Reads the httpOnly refresh-token cookie server-side; the browser never
 * supplies it directly. No cookie present -> 401, same shape as any other
 * auth failure, never a distinguishable signal.
 *
 * Reads via `request.cookies` (the NextRequest's own cookie jar) rather
 * than `next/headers`'s `cookies()` -- the latter requires Next's App
 * Router request-scope (AsyncLocalStorage) context, which only exists
 * when a request is dispatched through the real Next.js server; a Route
 * Handler already has the request object, so this is both the more
 * directly-testable and the more conventional choice for this call site.
 */
export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json(
      { error: "No session to refresh.", code: "NO_SESSION" },
      { status: 401 },
    );
  }
  return proxyRequest(`${IDENTITY_SERVICE_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}
