import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { RECIPE_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

function unauthenticated() {
  return NextResponse.json(
    { error: "Missing authenticated caller.", code: "UNAUTHENTICATED" },
    { status: 401 },
  );
}

export async function POST(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) return unauthenticated();
  const body = await request.json();
  return proxyRequest(`${RECIPE_SERVICE_BASE_URL}/api/v1/recipes`, {
    method: "POST",
    body,
    accessToken,
  });
}

// GET /api/recipes?mine=true -- only own-recipe listing is supported
// (recipe_routes.py's list_own_recipes requires mine=true), so this proxy
// always forwards that fixed query rather than relaying an arbitrary one.
export async function GET(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) return unauthenticated();
  return proxyRequest(`${RECIPE_SERVICE_BASE_URL}/api/v1/recipes?mine=true`, {
    method: "GET",
    accessToken,
  });
}
