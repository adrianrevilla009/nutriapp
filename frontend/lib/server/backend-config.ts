/**
 * Server-only backend base URLs. Read exclusively inside Route Handlers
 * (app/api/**\/route.ts) -- never imported from a Client Component, so
 * these hostnames never reach the browser bundle. Defaults match
 * docker-compose.yml's in-network service DNS names/ports; override via
 * .env.local for a non-compose local dev setup.
 */
// NOSONAR(typescript:S5332) x4 below -- these are in-cluster/in-compose
// service-to-service default hostnames, not a user-facing endpoint. TLS
// terminates at the edge (Kong/CloudFront, ADR-0010); every backend
// service in this repo listens on plain HTTP internally the same way.
// Genuine false positive, not a suppressed real finding.
export const IDENTITY_SERVICE_BASE_URL =
  process.env.IDENTITY_SERVICE_BASE_URL ?? "http://identity-service:8000"; // NOSONAR
export const CATALOG_SERVICE_BASE_URL =
  process.env.CATALOG_SERVICE_BASE_URL ?? "http://catalog-service:8000"; // NOSONAR
export const DIARY_SERVICE_BASE_URL =
  process.env.DIARY_SERVICE_BASE_URL ?? "http://diary-service:8000"; // NOSONAR
export const BFF_SERVICE_BASE_URL = process.env.BFF_SERVICE_BASE_URL ?? "http://bff-service:8000"; // NOSONAR

/** Name of the httpOnly cookie holding the opaque, server-revocable
 * refresh token (ADR-0022). Never read by client-side JS. */
export const REFRESH_TOKEN_COOKIE = "nutriapp_refresh_token";

/**
 * Whether the refresh-token cookie is set with the `Secure` attribute.
 *
 * Defaults to `true` (safe production default -- CloudFront/Kong terminate
 * TLS at the edge per ADR-0010, so the browser always sees an HTTPS origin
 * in a real deployment even though this pod itself listens on plain HTTP
 * internally, same as every backend service in this repo). Deliberately
 * NOT tied to `NODE_ENV` -- this app runs with `NODE_ENV=production` in
 * docker-compose for local dev too (a Next.js build-optimization flag, not
 * a TLS signal), and a real browser SILENTLY REFUSES to store a `Secure`
 * cookie set over a plain-HTTP connection -- confirmed empirically: this
 * exact bug caused the login flow to appear to succeed (200, a real access
 * token returned) while the browser never actually persisted the refresh
 * cookie, so middleware.ts's session check failed on the very next
 * navigation and silently bounced back to /login. Set `COOKIE_SECURE=false`
 * explicitly for any HTTP-only environment (local dev, docker-compose,
 * this Playwright E2E target).
 */
export const COOKIE_SECURE = process.env.COOKIE_SECURE !== "false";

/**
 * Extracts the real end-user's IP for forwarding to identity-service as
 * `X-Forwarded-For`, needed by any Route Handler proxying to an endpoint
 * identity-service rate-limits per client IP (login, register, password
 * reset -- application/commands/{login,register_user,request_password_reset}.py).
 *
 * REAL BUG, found via a live E2E run: without this, every proxied
 * request reaches identity-service from THIS APP'S OWN server, so
 * identity-service's `get_client_ip` (infrastructure/http/dependencies.py)
 * sees one shared IP for every real end user -- the rate-limit bucket
 * (10 logins/60s, 5 registers/60s) becomes shared across the whole
 * app's traffic, not per user. Confirmed reproducing this exact failure
 * mode while testing: repeated login attempts from automated testing
 * exhausted the shared bucket and caused a real seeded user's own correct-
 * password login to fail with the same generic "Invalid email or
 * password" text as a wrong password would (RateLimitedError maps to
 * IDENTICAL frontend-visible copy, application/commands/login.py's own
 * generic-error design intentionally does not distinguish these).
 *
 * If Kong/CloudFront (the real production edge, ADR-0010) already set
 * X-Forwarded-For on the incoming request, that value is trusted and
 * forwarded verbatim (Kong is the trust boundary). In local dev with no
 * edge in front of this app, no real per-browser IP is obtainable from a
 * Next.js Route Handler at all (the underlying socket isn't exposed) --
 * this is a documented, dev-only degradation, not something this fix
 * attempts to work around further.
 */
export function forwardedForHeader(request: Request): Record<string, string> {
  const existing = request.headers.get("x-forwarded-for");
  return existing ? { "X-Forwarded-For": existing } : {};
}
