import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { AppNav } from "@/components/features/AppNav";
import { setAccessToken } from "@/lib/session";

describe("AppNav", () => {
  beforeEach(() => {
    setAccessToken(null);
    // useSession's on-mount silent-refresh call -- no session cookie in
    // this test, so it always misses; mocked to keep the suite's
    // onUnhandledRequest:"error" guard clean.
    server.use(
      http.post("/api/auth/refresh", () =>
        HttpResponse.json({ error: "No session to refresh.", code: "NO_SESSION" }, { status: 401 }),
      ),
    );
  });

  it("renders nothing when signed out", () => {
    const { container } = renderWithProviders(<AppNav />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nav links when signed in", () => {
    setAccessToken("fixture-token");
    renderWithProviders(<AppNav />);
    expect(screen.getByRole("link", { name: /search/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("renders a journey 2 'Log from photo' link to /log/photo when signed in", () => {
    setAccessToken("fixture-token");
    renderWithProviders(<AppNav />);
    expect(screen.getByRole("link", { name: /log from photo/i })).toHaveAttribute(
      "href",
      "/log/photo",
    );
  });

  it("renders journey 3's 'Recipes' and 'Upgrade to Pro' links UNCONDITIONALLY when signed in -- no Pro-status branching exists (resolution 3)", () => {
    setAccessToken("fixture-token");
    renderWithProviders(<AppNav />);
    expect(screen.getByRole("link", { name: /^recipes$/i })).toHaveAttribute("href", "/recipes");
    expect(screen.getByRole("link", { name: /upgrade to pro/i })).toHaveAttribute("href", "/pro");
  });
});
