/**
 * Shared fetch wrapper used by every module under lib/api/. Per
 * implementation plan section 4 / resolution 1, every one of these calls
 * targets this frontend's OWN Route Handlers (app/api/*\/route.ts), never
 * a backend service origin directly from the browser -- those Route
 * Handlers are the ones that actually reach identity-service /
 * catalog-service / diary-service / bff-service, and are the sole holder
 * of any raw token (see lib/hooks/useSession.ts).
 */
import { ErrorResponseSchema } from "@/schemas/identity";

export class AppError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.status = status;
  }
}

export class TimeoutError extends AppError {
  constructor() {
    super("The request timed out.", "TIMEOUT", 0);
    this.name = "TimeoutError";
  }
}

const DEFAULT_TIMEOUT_MS = 8000;

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  accessToken?: string | null;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Additional headers to forward verbatim -- used by the login/register
   * Route Handlers to relay X-Forwarded-For so identity-service's
   * IP-keyed rate limiter sees each real end user, not this app's own
   * server-to-server proxy IP for every request (see
   * app/api/auth/login/route.ts's header comment -- a real bug found via
   * a live E2E run: every login/register attempt shared ONE rate-limit
   * bucket once proxied). */
  extraHeaders?: Record<string, string>;
}

/**
 * Parses a non-2xx response body into a typed AppError. Falls back to a
 * generic error (never throws an unhandled JSON-parse exception) when the
 * body isn't the documented {error, code} shape -- api-conventions
 * SKILL.md's error contract, but defensively, since a proxy/network layer
 * can return something else entirely (e.g. an HTML 502 page).
 */
async function parseErrorResponse(response: Response): Promise<AppError> {
  let raw: unknown;
  try {
    raw = await response.json();
  } catch {
    return new AppError("Something went wrong.", "UNKNOWN_ERROR", response.status);
  }
  const parsed = ErrorResponseSchema.safeParse(raw);
  if (!parsed.success) {
    return new AppError("Something went wrong.", "UNKNOWN_ERROR", response.status);
  }
  return new AppError(parsed.data.error, parsed.data.code, response.status);
}

export async function apiFetch<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const {
    method = "GET",
    body,
    accessToken,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    extraHeaders,
  } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json", ...extraHeaders };
  // Only ever attach the header when a real token string is present --
  // never a literal "Bearer undefined"/"Bearer null" (test-plan section 2).
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  // Allow an external signal (e.g. a caller-level cancel) to compose with
  // the internal timeout-driven abort.
  options.signal?.addEventListener("abort", () => controller.abort());

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch {
    // Checking `controller.signal.aborted` rather than sniffing the
    // thrown error's `name`/type is deliberate: different fetch
    // implementations (undici, jsdom's polyfill, MSW's interceptor) don't
    // consistently surface an `AbortError`-named DOMException here, but
    // the controller's own `aborted` flag is authoritative regardless.
    if (controller.signal.aborted) {
      throw new TimeoutError();
    }
    throw new AppError("Network request failed.", "NETWORK_ERROR", 0);
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }
  return (await response.json()) as TResponse;
}
