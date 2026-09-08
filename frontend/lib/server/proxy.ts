/**
 * Shared helper for every Route Handler proxy under app/api/**. Forwards a
 * request to a real backend service and relays either the parsed JSON body
 * (200) or the backend's own {error, code} shape (any non-2xx), preserving
 * the original status code -- so a client-side AppError (lib/api/http-client.ts)
 * still sees the real backend's error code, not a generic 500.
 */
import { NextResponse } from "next/server";
import { apiFetch, AppError } from "@/lib/api/http-client";

export async function proxyRequest<TResponse>(
  url: string,
  init: {
    method?: "GET" | "POST" | "PATCH" | "DELETE";
    body?: unknown;
    accessToken?: string | null;
    extraHeaders?: Record<string, string>;
  },
): Promise<NextResponse<TResponse | { error: string; code: string }>> {
  try {
    const data = await apiFetch<TResponse>(url, init);
    return NextResponse.json(data);
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
