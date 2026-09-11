/**
 * Browser-facing billing client -- calls this app's own
 * app/api/billing/checkout-sessions Route Handler (Route-Handler-proxy
 * pattern, journeys 1-2's resolution 1), which forwards to billing-service's
 * POST /api/v1/billing/checkout-sessions.
 *
 * This is a Stripe-HOSTED Checkout Session (confirmed by reading
 * checkout_routes.py/create_checkout_session.py directly): billing-service
 * never collects card data itself -- it returns a checkout_url the browser
 * navigates to. journey-3 resolution 1: no live Stripe round-trip is
 * possible in this environment (docker-compose.yml's Stripe keys are
 * UNSET_STRIPE_SECRET_KEY-style placeholders) -- this client's job ends at
 * correctly relaying checkout_url.
 */
import { apiFetch, AppError } from "@/lib/api/http-client";
import { CheckoutSessionResponseSchema, type CheckoutSessionResponse } from "@/schemas/billing";

/**
 * Distinguishable from a generic AppError via `instanceof`, never a
 * string-match on `.code` -- a 409 SUBSCRIPTION_ALREADY_ACTIVE means the
 * user is already Pro; the caller should redirect them, not show an error
 * banner (journey-3 test-plan section 2).
 */
export class AlreadyProError extends AppError {
  constructor(message: string) {
    super(message, "SUBSCRIPTION_ALREADY_ACTIVE", 409);
    this.name = "AlreadyProError";
  }
}

export interface CreateCheckoutSessionParams {
  successUrl: string;
  cancelUrl: string;
  customerEmail?: string | null;
}

export async function createCheckoutSession(
  { successUrl, cancelUrl, customerEmail }: CreateCheckoutSessionParams,
  accessToken: string,
): Promise<CheckoutSessionResponse> {
  try {
    const raw = await apiFetch<unknown>("/api/billing/checkout-sessions", {
      method: "POST",
      body: {
        success_url: successUrl,
        cancel_url: cancelUrl,
        customer_email: customerEmail ?? null,
      },
      accessToken,
    });
    return CheckoutSessionResponseSchema.parse(raw);
  } catch (err) {
    if (err instanceof AppError && err.code === "SUBSCRIPTION_ALREADY_ACTIVE") {
      throw new AlreadyProError(err.message);
    }
    throw err;
  }
}
