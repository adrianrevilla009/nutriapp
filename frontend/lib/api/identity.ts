/**
 * Browser-facing identity client. Every function here calls THIS app's own
 * Route Handlers under app/api/auth/[action]/route.ts, never
 * identity-service directly (implementation plan section 4 / resolution 1)
 * -- those handlers are the only code that ever sees a raw refresh token.
 */
import { apiFetch } from "@/lib/api/http-client";
import {
  BrowserLoginResultSchema,
  RefreshResponseSchema,
  RegisterResponseSchema,
  VerifyEmailResponseSchema,
  type BrowserLoginResult,
  type RefreshResponse,
  type RegisterResponse,
  type VerifyEmailResponse,
} from "@/schemas/identity";

export async function register(email: string, password: string): Promise<RegisterResponse> {
  const raw = await apiFetch<unknown>("/api/auth/register", {
    method: "POST",
    body: { email, password },
  });
  return RegisterResponseSchema.parse(raw);
}

export async function verifyEmail(
  referenceId: string,
  secret: string,
): Promise<VerifyEmailResponse> {
  const raw = await apiFetch<unknown>("/api/auth/verify-email", {
    method: "POST",
    body: { reference_id: referenceId, secret },
  });
  return VerifyEmailResponseSchema.parse(raw);
}

/**
 * On success, the Route Handler has already set the refresh token as an
 * httpOnly cookie -- only the access token is returned to browser JS, and
 * only `useSession` is meant to hold onto it (in memory, never
 * localStorage). Validated against BrowserLoginResultSchema, NOT
 * identity-service's own LoginResponseSchema -- see that schema's doc
 * comment (schemas/identity.ts) for the real bug this distinction fixes:
 * this app's own login Route Handler's response never carries
 * refresh_token, a genuinely different shape than the backend's.
 */
export async function login(email: string, password: string): Promise<BrowserLoginResult> {
  const raw = await apiFetch<unknown>("/api/auth/login", {
    method: "POST",
    body: { email, password },
  });
  return BrowserLoginResultSchema.parse(raw);
}

/** Reads the httpOnly refresh-token cookie server-side; no body needed. */
export async function refresh(): Promise<RefreshResponse> {
  const raw = await apiFetch<unknown>("/api/auth/refresh", { method: "POST" });
  return RefreshResponseSchema.parse(raw);
}

export async function logout(): Promise<void> {
  await apiFetch<unknown>("/api/auth/logout", { method: "POST" });
}
