/**
 * Zod schemas mirroring
 * services/billing-service/infrastructure/http/schemas/billing_schemas.py
 * field-for-field (journey 3, /plans/frontend/journey-3-implementation-plan.md
 * section 4).
 */
import { z } from "zod";

// Mirrors CheckoutSessionRequest: {success_url: str, cancel_url: str, customer_email: str | None}
export const CheckoutSessionRequestSchema = z.object({
  success_url: z.string().min(1),
  cancel_url: z.string().min(1),
  customer_email: z.string().nullable().optional(),
});
export type CheckoutSessionRequest = z.infer<typeof CheckoutSessionRequestSchema>;

// Mirrors CheckoutSessionResponse: {stripe_session_id: str, checkout_url: str}.
// This is a Stripe-HOSTED Checkout Session URL (checkout_routes.py's own
// docstring: "Never collects card data itself") -- the frontend's only job
// is to redirect the browser here, never to render a payment form.
export const CheckoutSessionResponseSchema = z.object({
  stripe_session_id: z.string().min(1),
  checkout_url: z.string().min(1),
});
export type CheckoutSessionResponse = z.infer<typeof CheckoutSessionResponseSchema>;
