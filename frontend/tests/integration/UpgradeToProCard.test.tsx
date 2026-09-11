import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { UpgradeToProCard } from "@/components/features/billing/UpgradeToProCard";
import { setAccessToken } from "@/lib/session";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("UpgradeToProCard", () => {
  beforeEach(() => {
    setAccessToken(null);
    server.use(
      http.post("/api/auth/refresh", () =>
        HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
      ),
    );
  });

  it("renders the Pro pitch and an Upgrade to Pro button", () => {
    renderWithProviders(<UpgradeToProCard />);
    expect(screen.getByRole("heading", { name: /upgrade to pro/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /upgrade to pro/i })).toBeInTheDocument();
  });

  it("has no critical/serious axe violations", async () => {
    const { container } = renderWithProviders(<UpgradeToProCard />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
