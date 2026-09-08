import { NextResponse, type NextRequest } from "next/server";
import {
  COOKIE_SECURE,
  forwardedForHeader,
  IDENTITY_SERVICE_BASE_URL,
  REFRESH_TOKEN_COOKIE,
} from "@/lib/server/backend-config";
import { apiFetch, AppError } from "@/lib/api/http-client";
import { LoginResponseSchema } from "@/schemas/identity";

/**
 * On success, sets the refresh token as an httpOnly/sameSite=lax cookie
 * (Secure by default, disable via COOKIE_SECURE=false for a plain-HTTP
 * environment -- see lib/server/backend-config.ts's COOKIE_SECURE doc
 * comment) and returns ONLY the access token to the browser -- the raw
 * refresh token never reaches client-side JS (implementation plan
 * section 4).
 *
 * Forwards X-Forwarded-For so identity-service's per-client-IP login rate
 * limiter (application/commands/login.py, 10/60s) sees each real end
 * user, not this proxy's own IP for every request -- see
 * lib/server/backend-config.ts's forwardedForHeader doc for the real bug
 * this fixes, found via a live E2E run (repeated automated login attempts
 * exhausted one shared bucket, causing an unrelated correct-password
 * login to fail with the same generic error text a rate-limit rejection
 * and a wrong password both produce).
 */
export async function POST(request: NextRequest) {
  const body = await request.json();
  try {
    const raw = await apiFetch<unknown>(`${IDENTITY_SERVICE_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      body,
      extraHeaders: forwardedForHeader(request),
    });
    const parsed = LoginResponseSchema.parse(raw);
    const response = NextResponse.json({
      access_token: parsed.access_token,
      token_type: parsed.token_type,
    });
    response.cookies.set(REFRESH_TOKEN_COOKIE, parsed.refresh_token, {
      httpOnly: true,
      secure: COOKIE_SECURE,
      sameSite: "lax",
      path: "/",
      // Mirrors identity-service's own REFRESH_TOKEN_TTL (30 days,
      // application/commands/login.py) -- the cookie's own lifetime is a
      // client-side convenience only; actual revocability lives server-side
      // in identity-service's token store (ADR-0022).
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  } catch (err) {
    if (err instanceof AppError) {
      const status = err.status >= 400 && err.status < 600 ? err.status : 502;
      return NextResponse.json({ error: err.message, code: err.code }, { status });
    }
    return NextResponse.json(
      { error: "Something went wrong.", code: "UNKNOWN_ERROR" },
      { status: 502 },
    );
  }
}
