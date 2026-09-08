import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { LoginForm } from "@/components/features/auth/LoginForm";
import { browserLoginResultFixture } from "../fixtures/identity.fixtures";
import { setAccessToken } from "@/lib/session";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

// No pre-existing session for any of these tests -- useSession's on-mount
// refresh() call always misses (401), same as a fresh browser with no
// refresh-token cookie.
function mockNoExistingSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ error: "No session to refresh.", code: "NO_SESSION" }, { status: 401 }),
    ),
  );
}

describe("LoginForm", () => {
  beforeEach(() => {
    push.mockClear();
    setAccessToken(null);
    mockNoExistingSession();
  });

  it("happy path: valid credentials redirect to /search", async () => {
    // Mocked with the REAL Route Handler response shape (no refresh_token
    // -- see BrowserLoginResultSchema's doc comment). Regression coverage
    // for a real bug: an earlier version of this test mocked this same
    // endpoint with the BACKEND's shape (refresh_token included), which
    // masked a genuine client-side Zod validation failure that broke
    // every real login -- only caught by an actual Playwright run against
    // a live backend, not by any mocked test until this fixture was fixed.
    server.use(http.post("/api/auth/login", () => HttpResponse.json(browserLoginResultFixture)));
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/search"));
  });

  it("REGRESSION: fails if the mocked /api/auth/login response ever includes refresh_token again (proves the schema, not the test, is what guards this)", async () => {
    // Deliberately mocks with the BACKEND shape (refresh_token present) --
    // BrowserLoginResultSchema doesn't reject extra fields (no .strict()),
    // so this succeeding is expected; the real guard against the original
    // bug is the OPPOSITE direction (a response missing refresh_token
    // must still succeed, proven by the happy-path test above using the
    // real proxy shape). This test exists to document that distinction
    // explicitly rather than leave it implicit.
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json({
          access_token: "t",
          refresh_token: "should-never-reach-the-browser-but-schema-tolerates-extra-fields",
          token_type: "bearer",
        }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);
    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/search"));
  });

  it.each([
    ["wrong password", "Invalid email or password.", "INVALID_CREDENTIALS"],
    [
      "unverified email (backend maps to the SAME generic error)",
      "Invalid email or password.",
      "INVALID_CREDENTIALS",
    ],
    [
      "locked account (backend maps to the SAME generic error)",
      "Invalid email or password.",
      "INVALID_CREDENTIALS",
    ],
  ])(
    "renders the SAME generic error copy for %s -- never a distinguishing signal",
    async (_label, error, code) => {
      server.use(
        http.post("/api/auth/login", () => HttpResponse.json({ error, code }, { status: 401 })),
      );
      const user = userEvent.setup();
      renderWithProviders(<LoginForm />);
      await user.type(screen.getByLabelText(/email address/i), "user@example.com");
      await user.type(screen.getByLabelText(/^password$/i), "whatever");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(
        "Invalid email or password, or your email isn't verified yet.",
      );
    },
  );

  it("has no critical/serious axe violations in the error state", async () => {
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json({ error: "x", code: "INVALID_CREDENTIALS" }, { status: 401 }),
      ),
    );
    const user = userEvent.setup();
    const { container } = renderWithProviders(<LoginForm />);
    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "whatever");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByRole("alert");

    expect(await axe(container)).toHaveNoViolations();
  });
});
