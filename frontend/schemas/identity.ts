/**
 * Zod schemas mirroring services/identity-service/infrastructure/http/schemas/auth_schemas.py
 * field-for-field (docs/frontend-architecture.md section 4). Every schema
 * here corresponds 1:1 to a Pydantic model in that file -- if that file
 * changes, this file changes in the same PR (CLAUDE.md section 4 /
 * architecture-agent's cross-boundary review concern).
 */
import { z } from "zod";

// Mirrors ErrorResponse: {error: str, code: str}. Uses .passthrough(),
// not .strict(): a future backend field addition (e.g. a "details" object)
// must not break every client that parses this shape -- forward
// compatibility over strictness for a shape the frontend never re-emits.
export const ErrorResponseSchema = z
  .object({
    error: z.string(),
    code: z.string(),
  })
  .passthrough();
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;

// Mirrors RegisterRequest: {email: EmailStr, password: str (min_length=1)}
export const RegisterRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;

// Mirrors RegisterResponse: {user_id: UUID}
export const RegisterResponseSchema = z.object({
  user_id: z.string().uuid(),
});
export type RegisterResponse = z.infer<typeof RegisterResponseSchema>;

// Mirrors VerifyEmailRequest: {reference_id: str, secret: str}
export const VerifyEmailRequestSchema = z.object({
  reference_id: z.string().min(1),
  secret: z.string().min(1),
});
export type VerifyEmailRequest = z.infer<typeof VerifyEmailRequestSchema>;

// Mirrors VerifyEmailResponse: {user_id: UUID}
export const VerifyEmailResponseSchema = z.object({
  user_id: z.string().uuid(),
});
export type VerifyEmailResponse = z.infer<typeof VerifyEmailResponseSchema>;

// Mirrors LoginRequest: {email: EmailStr, password: str (min_length=1)}
export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

// Mirrors LoginResponse: {access_token: str, refresh_token: str, token_type: str = "bearer"}.
// access_token/refresh_token are REQUIRED -- a response missing either is
// rejected by this schema, never silently coerced to undefined (test-plan
// section 1).
export const LoginResponseSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
  token_type: z.string().default("bearer"),
});
export type LoginResponse = z.infer<typeof LoginResponseSchema>;

// NOT a mirror of identity-service's own LoginResponse -- this is THIS
// APP'S OWN app/api/auth/login/route.ts response shape, which deliberately
// strips refresh_token before it ever reaches browser JS (implementation
// plan section 4: "the raw refresh token never reaches client-side JS").
// A REAL bug was found by validating this end-to-end against a live
// backend: lib/api/identity.ts's browser-facing login() was previously
// validating this proxy response against LoginResponseSchema (which
// REQUIRES refresh_token) -- since the proxy's real response never
// carries it, every real login call failed with a client-side Zod
// exception, silently masked by an MSW-mocked integration test that (also
// incorrectly) mocked the proxy endpoint with the full backend-shaped
// fixture, refresh_token included. This schema is the fix: the two
// contracts (identity-service's real response vs. this app's own
// browser-facing response) are genuinely different shapes and must not
// share a schema.
export const BrowserLoginResultSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string().default("bearer"),
});
export type BrowserLoginResult = z.infer<typeof BrowserLoginResultSchema>;

// Mirrors RefreshResponse: {access_token: str, token_type: str = "bearer"}
export const RefreshResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string().default("bearer"),
});
export type RefreshResponse = z.infer<typeof RefreshResponseSchema>;
