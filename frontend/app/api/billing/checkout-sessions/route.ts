import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { APP_BASE_URL, BILLING_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

/**
 * POST /api/billing/checkout-sessions -- proxies to billing-service's
 * hosted-Stripe-Checkout-session creation (checkout_routes.py).
 *
 * Builds ABSOLUTE success_url/cancel_url itself, from this app's OWN
 * server-side APP_BASE_URL, rather than trusting whatever the client body
 * sent (defense in depth -- these values determine where Stripe redirects
 * the browser after payment, so they must not be client-controllable).
 * The browser-side CheckoutRedirectButton independently builds the same
 * URLs for its own request body (test-plan section 3's assertion covers
 * that), but this handler is the actual source of truth.
 */
export async function POST(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) {
    return NextResponse.json(
      { error: "Missing authenticated caller.", code: "UNAUTHENTICATED" },
      { status: 401 },
    );
  }
  const body = await request.json().catch(() => ({}) as { customer_email?: string | null });
  return proxyRequest(`${BILLING_SERVICE_BASE_URL}/api/v1/billing/checkout-sessions`, {
    method: "POST",
    body: {
      success_url: `${APP_BASE_URL}/pro/success`,
      cancel_url: `${APP_BASE_URL}/pro/cancel`,
      customer_email: body?.customer_email ?? null,
    },
    accessToken,
  });
}
