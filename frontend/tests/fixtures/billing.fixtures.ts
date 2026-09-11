/**
 * Fixtures shaped from
 * services/billing-service/infrastructure/http/schemas/billing_schemas.py
 * (read verbatim during /implementation-plan's research). journey-3
 * test-plan section 4/8.
 */
import type { CheckoutSessionResponse } from "@/schemas/billing";

export const checkoutSessionResponseFixture: CheckoutSessionResponse = {
  stripe_session_id: "cs_test_fixture123",
  checkout_url: "https://checkout.stripe.com/c/pay/cs_test_fixture123",
};

export const alreadyActiveErrorFixture = {
  error: "User already has an active subscription.",
  code: "SUBSCRIPTION_ALREADY_ACTIVE",
};
