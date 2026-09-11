import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { renderWithProviders } from "./test-utils";
import { ProSuccessBanner } from "@/components/features/billing/ProSuccessBanner";
import { ProCancelBanner } from "@/components/features/billing/ProCancelBanner";

describe("ProSuccessBanner", () => {
  it("renders honest 'processing' copy -- NEVER a false 'You're now Pro!' confirmation (resolution 3: no way to verify this)", () => {
    renderWithProviders(<ProSuccessBanner sessionId="cs_test_fixture123" />);
    expect(screen.getByText(/payment received/i)).toBeInTheDocument();
    expect(screen.getByText(/activation can take a moment/i)).toBeInTheDocument();
    expect(screen.queryByText(/you're now pro/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/you are now pro/i)).not.toBeInTheDocument();
  });

  it("renders the same honest copy with no session_id present at all", () => {
    renderWithProviders(<ProSuccessBanner />);
    expect(screen.getByText(/payment received/i)).toBeInTheDocument();
  });

  it("links onward to starting a recipe", () => {
    renderWithProviders(<ProSuccessBanner sessionId="cs_test_fixture123" />);
    expect(screen.getByRole("link", { name: /start a recipe/i })).toHaveAttribute(
      "href",
      "/recipes/new",
    );
  });

  it("has no critical/serious axe violations", async () => {
    const { container } = renderWithProviders(<ProSuccessBanner sessionId="cs_test_fixture123" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("ProCancelBanner", () => {
  it("renders neutral 'no charge was made' copy, with a link back to /pro", () => {
    renderWithProviders(<ProCancelBanner />);
    expect(screen.getByText(/no charge was made/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to pro/i })).toHaveAttribute("href", "/pro");
  });

  it("has no critical/serious axe violations", async () => {
    const { container } = renderWithProviders(<ProCancelBanner />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
