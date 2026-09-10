import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { FOOD_RECOGNITION_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { MAX_UPLOAD_BYTES } from "@/lib/photo-upload-constraints";

export { MAX_UPLOAD_BYTES };

/**
 * Multipart Route Handler proxy for
 * POST /api/v1/recognition/photos/analyze (food-recognition-service).
 *
 * Deliberately does NOT reuse lib/server/proxy.ts's proxyRequest/apiFetch
 * -- both are JSON-only (apiFetch unconditionally sets
 * `Content-Type: application/json` and JSON.stringifies the body), which
 * is incompatible with a multipart upload. This handler buffers the
 * incoming upload once (via request.formData()) and re-POSTs it as a
 * fresh FormData -- the pragmatic first-cut choice for phone-photo scale
 * (journey 2 implementation plan section 4/9.6); a raw-streamed relay is
 * a documented future optimization, not built here.
 */

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

function errorResponse(status: number, error: string, code: string) {
  return NextResponse.json({ error, code }, { status });
}

export async function POST(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) {
    return errorResponse(401, "Missing authenticated caller.", "UNAUTHENTICATED");
  }

  let incoming: FormData;
  try {
    incoming = await request.formData();
  } catch {
    return errorResponse(422, "Malformed upload.", "INVALID_IMAGE");
  }

  const file = incoming.get("file");
  if (!(file instanceof Blob)) {
    return errorResponse(422, "No photo was uploaded.", "INVALID_IMAGE");
  }
  if (file.size === 0) {
    return errorResponse(422, "Uploaded photo is empty.", "INVALID_IMAGE");
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return errorResponse(413, "Photo is too large.", "PHOTO_TOO_LARGE");
  }

  const forwardBody = new FormData();
  const filename = file instanceof File ? file.name : "photo";
  forwardBody.append("file", file, filename);

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${FOOD_RECOGNITION_SERVICE_BASE_URL}/api/v1/recognition/photos/analyze`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: forwardBody,
      },
    );
  } catch {
    return errorResponse(502, "Something went wrong.", "UNKNOWN_ERROR");
  }

  let body: unknown;
  try {
    body = await backendResponse.json();
  } catch {
    return errorResponse(502, "Something went wrong.", "UNKNOWN_ERROR");
  }

  if (!backendResponse.ok) {
    const status =
      backendResponse.status >= 400 && backendResponse.status < 600 ? backendResponse.status : 502;
    return NextResponse.json(body, { status });
  }

  return NextResponse.json(body);
}
