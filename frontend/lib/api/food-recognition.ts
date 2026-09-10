/**
 * Browser-facing food-recognition client -- calls this app's own
 * app/api/food-recognition/photos/analyze Route Handler (journey 2
 * implementation plan section 4, resolution 1's proxy pattern extended).
 *
 * Deliberately does NOT go through lib/api/http-client.ts's apiFetch:
 * apiFetch unconditionally sets `Content-Type: application/json` and
 * JSON.stringifies its body, which would corrupt a multipart upload. This
 * module duplicates the minimal pieces of apiFetch's behavior it needs
 * (timeout handling, {error, code} parsing) -- a small, deliberate,
 * documented duplication, not a silent divergence.
 */
import { AppError, TimeoutError } from "@/lib/api/http-client";
import { ErrorResponseSchema } from "@/schemas/identity";
import { AnalyzePhotoResponseSchema, type AnalyzePhotoResponse } from "@/schemas/food-recognition";

// food-recognition-service's own documented resilience budget (README.md:
// purgatory fail_max=5 / tenacity 3 attempts / 5s connect, 20s read on the
// Claude vision call) can legitimately exceed http-client.ts's shared
// 8000ms DEFAULT_TIMEOUT_MS well before it degrades to
// status: "unavailable" -- this call needs its own, longer budget.
export const ANALYZE_PHOTO_TIMEOUT_MS = 45_000;

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

export async function analyzeFoodPhoto(
  file: File,
  accessToken: string,
  timeoutMs: number = ANALYZE_PHOTO_TIMEOUT_MS,
): Promise<AnalyzePhotoResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch("/api/food-recognition/photos/analyze", {
      method: "POST",
      // No Content-Type header set manually -- the browser sets
      // multipart/form-data with the correct boundary parameter itself.
      // Setting one explicitly here is a real bug class that silently
      // drops the boundary and breaks the upload.
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      body: formData,
      signal: controller.signal,
    });
  } catch {
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
  const raw = await response.json();
  return AnalyzePhotoResponseSchema.parse(raw);
}
