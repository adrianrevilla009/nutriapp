import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { RegisterForm } from "@/components/features/auth/RegisterForm";
import { registerResponseFixture } from "../fixtures/identity.fixtures";

describe("RegisterForm", () => {
  it("happy path: valid email/password succeeds and shows the check-your-email state", async () => {
    server.use(http.post("/api/auth/register", () => HttpResponse.json(registerResponseFixture)));
    const user = userEvent.setup();
    renderWithProviders(<RegisterForm />);

    await user.type(screen.getByLabelText(/email address/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "a-real-password");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
    expect(screen.getByText(/new@example\.com/)).toBeInTheDocument();
  });

  it("blocks submission client-side on an invalid email, making zero network calls", async () => {
    let callCount = 0;
    server.use(
      http.post("/api/auth/register", () => {
        callCount += 1;
        return HttpResponse.json(registerResponseFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterForm />);

    await user.type(screen.getByLabelText(/email address/i), "not-an-email");
    await user.type(screen.getByLabelText(/^password$/i), "a-real-password");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(callCount).toBe(0);
  });

  it("blocks submission client-side on an empty password", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterForm />);
    await user.type(screen.getByLabelText(/email address/i), "new@example.com");
    await user.click(screen.getByRole("button", { name: /register/i }));
    expect(await screen.findByText(/enter a password/i)).toBeInTheDocument();
  });

  it("renders a visible error banner on a mocked 4xx from the register endpoint", async () => {
    server.use(
      http.post("/api/auth/register", () =>
        HttpResponse.json(
          { error: "Email already registered.", code: "EMAIL_TAKEN" },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterForm />);
    await user.type(screen.getByLabelText(/email address/i), "dupe@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "a-real-password");
    await user.click(screen.getByRole("button", { name: /register/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/already registered/i);
  });

  it("disables the submit button while the request is in flight (guards double-submit)", async () => {
    server.use(
      http.post("/api/auth/register", async () => {
        await new Promise((resolve) => setTimeout(resolve, 30));
        return HttpResponse.json(registerResponseFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterForm />);
    await user.type(screen.getByLabelText(/email address/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "a-real-password");
    const submitButton = screen.getByRole("button", { name: /register/i });
    await user.click(submitButton);

    await waitFor(() => expect(screen.getByRole("button")).toBeDisabled());
  });

  it("has no critical/serious axe violations in its initial state", async () => {
    const { container } = renderWithProviders(<RegisterForm />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no critical/serious axe violations in its error state", async () => {
    server.use(
      http.post("/api/auth/register", () =>
        HttpResponse.json(
          { error: "Email already registered.", code: "EMAIL_TAKEN" },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    const { container } = renderWithProviders(<RegisterForm />);
    await user.type(screen.getByLabelText(/email address/i), "dupe@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "a-real-password");
    await user.click(screen.getByRole("button", { name: /register/i }));
    await screen.findByRole("alert");

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
