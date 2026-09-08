import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { POST as loginRoute } from "@/app/api/auth/login/route";
import { POST as refreshRoute } from "@/app/api/auth/refresh/route";
import { loginResponseFixture } from "../fixtures/identity.fixtures";
import { REFRESH_TOKEN_COOKIE } from "@/lib/server/backend-config";

/**
 * Route Handlers are the resolution-1 proxy boundary (implementation plan
 * section 4/5) -- invoked directly here (no full Next server needed; a
 * Route Handler is a plain async function taking a (Next)Request) against
 * a mocked identity-service backend, proving the httpOnly-cookie contract
 * end-to-end without a live backend.
 */
describe("app/api/auth/login route handler", () => {
  it("sets an httpOnly refresh-token cookie and returns ONLY the access token", async () => {
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/login", () =>
        HttpResponse.json(loginResponseFixture),
      ),
    );
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.com", password: "x" }),
    });
    const response = await loginRoute(request);
    const body = await response.json();

    expect(body).toEqual({ access_token: loginResponseFixture.access_token, token_type: "bearer" });
    expect(body.refresh_token).toBeUndefined();

    const setCookie = response.cookies.get(REFRESH_TOKEN_COOKIE);
    expect(setCookie?.value).toBe(loginResponseFixture.refresh_token);
    expect(setCookie?.httpOnly).toBe(true);
    // Safe-by-default: Secure unless COOKIE_SECURE=false is set explicitly
    // (regression test for a real bug found via a live Playwright run --
    // see lib/server/backend-config.ts's COOKIE_SECURE doc comment).
    expect(setCookie?.secure).toBe(true);
  });

  it("forwards X-Forwarded-For to identity-service when the incoming request carries one", async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/login", ({ request }) => {
        capturedHeader = request.headers.get("x-forwarded-for");
        return HttpResponse.json(loginResponseFixture);
      }),
    );
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      headers: { "x-forwarded-for": "203.0.113.9" },
      body: JSON.stringify({ email: "a@example.com", password: "x" }),
    });
    await loginRoute(request);
    expect(capturedHeader).toBe("203.0.113.9");
  });

  it("relays the backend's real error code/status on failure", async () => {
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/login", () =>
        HttpResponse.json(
          { error: "Invalid email or password.", code: "INVALID_CREDENTIALS" },
          { status: 401 },
        ),
      ),
    );
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.com", password: "wrong" }),
    });
    const response = await loginRoute(request);
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({
      error: "Invalid email or password.",
      code: "INVALID_CREDENTIALS",
    });
  });
});

describe("app/api/auth/refresh route handler", () => {
  it("returns 401 with no upstream call when no refresh-token cookie is present", async () => {
    let called = false;
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/refresh", () => {
        called = true;
        return HttpResponse.json({ access_token: "x", token_type: "bearer" });
      }),
    );
    const request = new NextRequest("http://localhost/api/auth/refresh", { method: "POST" });
    const response = await refreshRoute(request);
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("forwards the cookie's refresh token to identity-service when present", async () => {
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/refresh", async ({ request }) => {
        const body = (await request.json()) as { refresh_token: string };
        expect(body.refresh_token).toBe("cookie-refresh-token");
        return HttpResponse.json({ access_token: "new-access-token", token_type: "bearer" });
      }),
    );
    const request = new NextRequest("http://localhost/api/auth/refresh", {
      method: "POST",
      headers: { cookie: `${REFRESH_TOKEN_COOKIE}=cookie-refresh-token` },
    });
    const response = await refreshRoute(request);
    expect(await response.json()).toEqual({
      access_token: "new-access-token",
      token_type: "bearer",
    });
  });
});
