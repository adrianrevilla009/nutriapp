import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { VerifyEmailStatus } from "@/components/features/auth/VerifyEmailStatus";
import { verifyEmailResponseFixture } from "../fixtures/identity.fixtures";

const mockSearchParams = vi.hoisted(() => ({ current: new URLSearchParams() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams.current,
}));

describe("VerifyEmailStatus", () => {
  it("renders 'invalid link' and makes ZERO API calls when reference_id/secret are missing", async () => {
    let callCount = 0;
    server.use(
      http.post("/api/auth/verify-email", () => {
        callCount += 1;
        return HttpResponse.json(verifyEmailResponseFixture);
      }),
    );
    mockSearchParams.current = new URLSearchParams();
    renderWithProviders(<VerifyEmailStatus />);

    expect(await screen.findByText(/invalid or incomplete/i)).toBeInTheDocument();
    expect(callCount).toBe(0);
  });

  it("calls verify-email exactly once for valid params, including under a remount", async () => {
    let callCount = 0;
    server.use(
      http.post("/api/auth/verify-email", () => {
        callCount += 1;
        return HttpResponse.json(verifyEmailResponseFixture);
      }),
    );
    mockSearchParams.current = new URLSearchParams({ reference_id: "r1", secret: "s1" });
    const { unmount } = renderWithProviders(<VerifyEmailStatus />);
    await screen.findByText(/verified/i);
    unmount();

    expect(callCount).toBe(1);
  });

  it("shows a distinct failure message on an already-used/expired token, still linking to /login", async () => {
    server.use(
      http.post("/api/auth/verify-email", () =>
        HttpResponse.json({ error: "Token expired.", code: "TOKEN_EXPIRED" }, { status: 410 }),
      ),
    );
    mockSearchParams.current = new URLSearchParams({ reference_id: "r1", secret: "s1" });
    renderWithProviders(<VerifyEmailStatus />);

    expect(await screen.findByText(/couldn't verify/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in/i })).toBeInTheDocument();
  });

  it("has no critical/serious axe violations in the invalid-link state", async () => {
    mockSearchParams.current = new URLSearchParams();
    const { container } = renderWithProviders(<VerifyEmailStatus />);
    await screen.findByText(/invalid or incomplete/i);
    expect(await axe(container)).toHaveNoViolations();
  });
});
