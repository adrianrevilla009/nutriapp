import type { NextRequest } from "next/server";
import { forwardedForHeader, IDENTITY_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

/**
 * Forwards X-Forwarded-For (when a real edge already set it) so
 * identity-service's per-client-IP register rate limiter
 * (application/commands/register_user.py, 5/60s) sees each real end
 * user, not this proxy's own IP for every request -- see
 * lib/server/backend-config.ts's forwardedForHeader doc for the real bug
 * this fixes (found via a live E2E run against the login endpoint, same
 * IP-keyed rate-limiter pattern applies here).
 */
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyRequest(`${IDENTITY_SERVICE_BASE_URL}/api/v1/auth/register`, {
    method: "POST",
    body,
    extraHeaders: forwardedForHeader(request),
  });
}
