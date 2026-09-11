import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { RECIPE_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

// GET /api/recipes/search?q=... -- proxies to recipe-service's Pro-gated
// cross-user search (search_routes.py). Blocks an empty/missing q BEFORE
// any downstream call, mirroring catalog search's min_length=1 guard
// (test-plan section 3).
export async function GET(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) {
    return NextResponse.json(
      { error: "Missing authenticated caller.", code: "UNAUTHENTICATED" },
      { status: 401 },
    );
  }
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q")?.trim();
  if (!q) {
    return NextResponse.json(
      { error: "A search query is required.", code: "INVALID_QUERY" },
      { status: 422 },
    );
  }
  const params = new URLSearchParams({ q });
  return proxyRequest(`${RECIPE_SERVICE_BASE_URL}/api/v1/recipes/search?${params.toString()}`, {
    method: "GET",
    accessToken,
  });
}
