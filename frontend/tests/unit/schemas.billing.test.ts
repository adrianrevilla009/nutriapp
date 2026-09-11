import { describe, expect, it } from "vitest";
import { CheckoutSessionRequestSchema, CheckoutSessionResponseSchema } from "@/schemas/billing";
import { checkoutSessionResponseFixture } from "../fixtures/billing.fixtures";

describe("CheckoutSessionRequestSchema", () => {
  it("parses a request with all fields", () => {
    const request = {
      success_url: "http://localhost:3000/pro/success",
      cancel_url: "http://localhost:3000/pro/cancel",
      customer_email: "user@example.com",
    };
    expect(CheckoutSessionRequestSchema.parse(request)).toEqual(request);
  });

  it("accepts a request with no customer_email", () => {
    const request = {
      success_url: "http://localhost:3000/pro/success",
      cancel_url: "http://localhost:3000/pro/cancel",
    };
    expect(() => CheckoutSessionRequestSchema.parse(request)).not.toThrow();
  });

  it("rejects a missing success_url", () => {
    expect(() =>
      CheckoutSessionRequestSchema.parse({ cancel_url: "http://localhost:3000/pro/cancel" }),
    ).toThrow();
  });
});

describe("CheckoutSessionResponseSchema", () => {
  it("parses a real-shaped checkout session response", () => {
    expect(CheckoutSessionResponseSchema.parse(checkoutSessionResponseFixture)).toEqual(
      checkoutSessionResponseFixture,
    );
  });

  it("rejects a response missing checkout_url", () => {
    expect(() => CheckoutSessionResponseSchema.parse({ stripe_session_id: "cs_test_x" })).toThrow();
  });
});
