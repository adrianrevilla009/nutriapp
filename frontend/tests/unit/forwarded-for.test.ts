import { describe, expect, it } from "vitest";
import { forwardedForHeader } from "@/lib/server/backend-config";

/**
 * Regression test for a REAL production-impacting bug found via a live
 * E2E run: identity-service's login/register rate limiters are keyed by
 * client IP (application/commands/{login,register_user}.py). Proxying
 * every request through this app's own server (resolution 1) means
 * identity-service would see ONE shared IP for every real end user unless
 * this app forwards the real one via X-Forwarded-For -- without this fix,
 * one busy period of app traffic (or, as observed directly, repeated
 * automated testing) exhausts a SHARED rate-limit bucket and locks out
 * unrelated users' correct-password logins with the same generic error a
 * wrong password produces.
 */
describe("forwardedForHeader", () => {
  it("forwards an existing X-Forwarded-For header verbatim (trusts the real edge, ADR-0010)", () => {
    const request = new Request("http://localhost/api/auth/login", {
      headers: { "x-forwarded-for": "203.0.113.7" },
    });
    expect(forwardedForHeader(request)).toEqual({ "X-Forwarded-For": "203.0.113.7" });
  });

  it("returns an empty header set when none is present (no per-browser IP obtainable in local dev)", () => {
    const request = new Request("http://localhost/api/auth/login");
    expect(forwardedForHeader(request)).toEqual({});
  });
});
