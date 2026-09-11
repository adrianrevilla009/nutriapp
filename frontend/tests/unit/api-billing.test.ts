import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { AppError } from "@/lib/api/http-client";
import { AlreadyProError, createCheckoutSession } from "@/lib/api/billing";
import {
  checkoutSessionResponseFixture,
  alreadyActiveErrorFixture,
} from "../fixtures/billing.fixtures";

describe("createCheckoutSession", () => {
  it("posts the exact request shape and parses a real-shaped response", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("/api/billing/checkout-sessions", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(checkoutSessionResponseFixture, { status: 201 });
      }),
    );
    const result = await createCheckoutSession(
      {
        successUrl: "http://localhost:3000/pro/success",
        cancelUrl: "http://localhost:3000/pro/cancel",
      },
      "fixture-token",
    );
    expect(capturedBody).toEqual({
      success_url: "http://localhost:3000/pro/success",
      cancel_url: "http://localhost:3000/pro/cancel",
      customer_email: null,
    });
    expect(result).toEqual(checkoutSessionResponseFixture);
  });

  it("maps a 409 SUBSCRIPTION_ALREADY_ACTIVE into a distinguishable AlreadyProError, not a generic AppError", async () => {
    server.use(
      http.post("/api/billing/checkout-sessions", () =>
        HttpResponse.json(alreadyActiveErrorFixture, { status: 409 }),
      ),
    );
    const error = await createCheckoutSession(
      {
        successUrl: "http://localhost:3000/pro/success",
        cancelUrl: "http://localhost:3000/pro/cancel",
      },
      "fixture-token",
    ).catch((e) => e);
    expect(error).toBeInstanceOf(AlreadyProError);
    expect(error).toBeInstanceOf(AppError);
  });

  it("maps every other error code to the generic AppError, not AlreadyProError (contrast test)", async () => {
    server.use(
      http.post("/api/billing/checkout-sessions", () =>
        HttpResponse.json({ error: "boom", code: "INTERNAL_ERROR" }, { status: 500 }),
      ),
    );
    const error = await createCheckoutSession(
      {
        successUrl: "http://localhost:3000/pro/success",
        cancelUrl: "http://localhost:3000/pro/cancel",
      },
      "fixture-token",
    ).catch((e) => e);
    expect(error).not.toBeInstanceOf(AlreadyProError);
    expect(error).toBeInstanceOf(AppError);
  });
});
