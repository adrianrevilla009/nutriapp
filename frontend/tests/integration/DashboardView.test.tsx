import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { DashboardView } from "@/components/features/dashboard/DashboardView";
import {
  allAvailableDashboardFixture,
  mixedAvailabilityDashboardFixture,
} from "../fixtures/bff.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("DashboardView", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("renders all three sections' real numbers when all are available", async () => {
    server.use(
      http.get("/api/bff/dashboard", () => HttpResponse.json(allAvailableDashboardFixture)),
    );
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText(/610 kcal/)).toBeInTheDocument();
    expect(screen.getByText(/1200 ml/)).toBeInTheDocument();
    expect(screen.getByText(/2000 kcal/)).toBeInTheDocument();
  });

  it("renders each unavailable section independently, with DISTINCT copy per reason", async () => {
    server.use(
      http.get("/api/bff/dashboard", () => HttpResponse.json(mixedAvailabilityDashboardFixture)),
    );
    renderWithProviders(<DashboardView />);

    // diary_summary is still "available" in the mixed fixture -- its real
    // number still renders even though the other two sections are down.
    await screen.findByText(/1200 ml/);

    const downstreamErrorMessages = await screen.findAllByText(/couldn't be loaded/i);
    const notYetComputedMessages = screen.getAllByText(/still catching up/i);
    expect(downstreamErrorMessages.length).toBeGreaterThan(0);
    expect(notYetComputedMessages.length).toBeGreaterThan(0);
    // The two reasons must never collapse to the same text.
    expect(downstreamErrorMessages[0]?.textContent).not.toEqual(
      notYetComputedMessages[0]?.textContent,
    );
  });

  it("the manual Refresh control triggers a real refetch (fetch call count increases)", async () => {
    let callCount = 0;
    server.use(
      http.get("/api/bff/dashboard", () => {
        callCount += 1;
        return HttpResponse.json(allAvailableDashboardFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<DashboardView />);
    await screen.findByText(/610 kcal/);
    const countAfterInitialLoad = callCount;

    await user.click(screen.getByRole("button", { name: /refresh/i }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(callCount).toBeGreaterThan(countAfterInitialLoad);
  });

  it("has no critical/serious axe violations with all sections available", async () => {
    server.use(
      http.get("/api/bff/dashboard", () => HttpResponse.json(allAvailableDashboardFixture)),
    );
    const { container } = renderWithProviders(<DashboardView />);
    await screen.findByText(/610 kcal/);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no critical/serious axe violations with mixed section availability", async () => {
    server.use(
      http.get("/api/bff/dashboard", () => HttpResponse.json(mixedAvailabilityDashboardFixture)),
    );
    const { container } = renderWithProviders(<DashboardView />);
    await screen.findByText(/1200 ml/);
    expect(await axe(container)).toHaveNoViolations();
  });
});
