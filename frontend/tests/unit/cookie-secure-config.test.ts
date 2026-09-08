import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Regression test for a REAL bug discovered via a live Playwright run
 * against docker-compose: the login flow returned 200 with a real access
 * token (curl-verified, looked fine), but a real browser silently refused
 * to PERSIST the refresh-token cookie because it was marked `Secure` over
 * a plain-HTTP origin -- the next navigation's middleware session check
 * then failed and silently bounced back to /login. Fixed by making the
 * `Secure` attribute driven by a dedicated `COOKIE_SECURE` env var
 * (default true/secure) instead of `NODE_ENV === "production"` (which
 * this app runs with even in plain-HTTP local dev, for Next's own build
 * optimizations -- not a TLS signal). See lib/server/backend-config.ts.
 */
describe("COOKIE_SECURE", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("defaults to true (secure) when COOKIE_SECURE is unset", async () => {
    vi.stubEnv("COOKIE_SECURE", undefined as unknown as string);
    vi.resetModules();
    const { COOKIE_SECURE } = await import("@/lib/server/backend-config");
    expect(COOKIE_SECURE).toBe(true);
  });

  it("is false only when explicitly set to the string 'false'", async () => {
    vi.stubEnv("COOKIE_SECURE", "false");
    vi.resetModules();
    const { COOKIE_SECURE } = await import("@/lib/server/backend-config");
    expect(COOKIE_SECURE).toBe(false);
  });

  it("stays true for any other value (fail safe, not fail open)", async () => {
    vi.stubEnv("COOKIE_SECURE", "no");
    vi.resetModules();
    const { COOKIE_SECURE } = await import("@/lib/server/backend-config");
    expect(COOKIE_SECURE).toBe(true);
  });
});
