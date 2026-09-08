/**
 * In-memory access-token store + refresh-scheduling pure function
 * (implementation plan section 4 / test-plan section 2).
 *
 * The access token is held ONLY in this module-level variable -- never
 * `localStorage`, never a plain (non-httpOnly) cookie. A hard page reload
 * loses it by design; `useSession` calls `refresh()` (backed by the
 * httpOnly refresh-token cookie, invisible to this code) to mint a new one
 * transparently on load.
 */

// ADR-0022: access tokens are short-lived, 15 minutes by default.
export const ACCESS_TOKEN_LIFETIME_SECONDS = 15 * 60;
// Refresh a safety margin before actual expiry, never right at the edge.
export const REFRESH_MARGIN_SECONDS = 60;

/** Pure: given when a token was issued, when should it be proactively
 * refreshed? Deterministic for a given `issuedAt` -- same input twice
 * yields the same result (test-plan section 2). */
export function computeRefreshDueAt(issuedAt: Date): Date {
  return new Date(
    issuedAt.getTime() + (ACCESS_TOKEN_LIFETIME_SECONDS - REFRESH_MARGIN_SECONDS) * 1000,
  );
}

interface SessionState {
  accessToken: string | null;
  issuedAt: Date | null;
}

let state: SessionState = { accessToken: null, issuedAt: null };
const listeners = new Set<() => void>();

export function getSessionState(): SessionState {
  return state;
}

export function setAccessToken(accessToken: string | null, issuedAt: Date = new Date()): void {
  state = { accessToken, issuedAt: accessToken ? issuedAt : null };
  listeners.forEach((listener) => listener());
}

export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
