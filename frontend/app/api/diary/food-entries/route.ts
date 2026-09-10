import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { DIARY_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

export async function POST(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) {
    return NextResponse.json(
      { error: "Missing authenticated caller.", code: "UNAUTHENTICATED" },
      { status: 401 },
    );
  }
  const body = await request.json();
  // Forwarded verbatim to diary-service (infrastructure/http/dependencies.py's
  // get_correlation_id reads this header, falling back to a generated
  // UUID) -- journey 2's LogFoodEntryForm sets this to the food-recognition
  // analysis_id for AI-sourced entries (architecture-agent finding).
  const correlationId = request.headers.get("X-Correlation-Id");
  return proxyRequest(`${DIARY_SERVICE_BASE_URL}/api/v1/diary/food-entries`, {
    method: "POST",
    body,
    accessToken,
    extraHeaders: correlationId ? { "X-Correlation-Id": correlationId } : undefined,
  });
}
