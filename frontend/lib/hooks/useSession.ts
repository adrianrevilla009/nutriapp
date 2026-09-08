"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import * as identity from "@/lib/api/identity";
import { getSessionState, setAccessToken, subscribeSession } from "@/lib/session";

/**
 * Session hook (implementation plan section 4): the access token lives in
 * lib/session.ts's module-level store (in memory only). On mount, if no
 * token is held yet, attempts a silent refresh backed by the httpOnly
 * refresh-token cookie the login Route Handler set -- so a hard reload
 * transparently re-establishes a session without ever touching
 * localStorage.
 */
export function useSession() {
  const queryClient = useQueryClient();
  const session = useSyncExternalStore(
    subscribeSession,
    getSessionState,
    () => ({ accessToken: null, issuedAt: null }) as ReturnType<typeof getSessionState>,
  );

  useEffect(() => {
    if (session.accessToken) return;
    let cancelled = false;
    identity
      .refresh()
      .then((result) => {
        if (!cancelled) setAccessToken(result.access_token);
      })
      .catch(() => {
        // No valid refresh-token cookie (never logged in, or it expired/was
        // revoked) -- fail closed, stay signed out. Never throw here; the
        // caller reads `accessToken === null` as "signed out".
      });
    return () => {
      cancelled = true;
    };
    // Intentionally runs once per mount, not on every accessToken change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await identity.login(email, password);
    setAccessToken(result.access_token);
    return result;
  }, []);

  const logout = useCallback(async () => {
    await identity.logout();
    setAccessToken(null);
    queryClient.clear();
  }, [queryClient]);

  return {
    accessToken: session.accessToken,
    isAuthenticated: session.accessToken !== null,
    login,
    logout,
  };
}
