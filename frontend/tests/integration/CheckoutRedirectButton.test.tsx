import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { CheckoutRedirectButton } from "@/components/features/billing/CheckoutRedirectButton";
import {
  checkoutSessionResponseFixture,
  alreadyActiveErrorFixture,
} from "../fixtures/billing.fixtures";
import { setAccessToken } from "@/lib/session";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("CheckoutRedirectButton", () => {
  let assignSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    push.mockClear();
    setAccessToken(null);
    mockAuthenticatedSession();
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, assign: assignSpy, origin: "http://localhost:3000" },
    });
  });

  it("on success, redirects the browser to the exact checkout_url returned -- never just renders it as a link", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("/api/billing/checkout-sessions", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(checkoutSessionResponseFixture, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CheckoutRedirectButton />);

    await user.click(screen.getByRole("button", { name: /upgrade to pro/i }));

    await vi.waitFor(() =>
      expect(assignSpy).toHaveBeenCalledWith(checkoutSessionResponseFixture.checkout_url),
    );
    expect(capturedBody).toMatchObject({
      success_url: "http://localhost:3000/pro/success",
      cancel_url: "http://localhost:3000/pro/cancel",
    });
  });

  it("on a 409 already-Pro response, navigates to /recipes with a message -- never calls window.location.assign", async () => {
    server.use(
      http.post("/api/billing/checkout-sessions", () =>
        HttpResponse.json(alreadyActiveErrorFixture, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<CheckoutRedirectButton />);

    await user.click(screen.getByRole("button", { name: /upgrade to pro/i }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/recipes?alreadyPro=1"));
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("on a generic backend failure, shows the error banner -- never redirects", async () => {
    server.use(
      http.post("/api/billing/checkout-sessions", () =>
        HttpResponse.json({ error: "boom", code: "PAYMENT_PROVIDER_UNAVAILABLE" }, { status: 503 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<CheckoutRedirectButton />);

    await user.click(screen.getByRole("button", { name: /upgrade to pro/i }));

    await screen.findByRole("alert");
    expect(assignSpy).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("disables the button while the request is pending (double-submit guard)", async () => {
    server.use(
      http.post("/api/billing/checkout-sessions", async () => {
        await new Promise((resolve) => setTimeout(resolve, 30));
        return HttpResponse.json(checkoutSessionResponseFixture, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CheckoutRedirectButton />);

    const button = screen.getByRole("button", { name: /upgrade to pro/i });
    await user.click(button);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
