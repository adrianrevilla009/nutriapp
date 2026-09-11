import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { RECIPE_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ recipeId: string }> },
) {
  const accessToken = bearerToken(request);
  if (!accessToken) {
    return NextResponse.json(
      { error: "Missing authenticated caller.", code: "UNAUTHENTICATED" },
      { status: 401 },
    );
  }
  const { recipeId } = await params;
  return proxyRequest(
    `${RECIPE_SERVICE_BASE_URL}/api/v1/recipes/${encodeURIComponent(recipeId)}/unpublish`,
    { method: "POST", accessToken },
  );
}
