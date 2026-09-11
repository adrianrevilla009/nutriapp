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

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ recipeId: string }> },
) {
  const accessToken = bearerToken(request);
  if (!accessToken) return unauthenticated();
  const { recipeId } = await params;
  return proxyRequest(`${RECIPE_SERVICE_BASE_URL}/api/v1/recipes/${encodeURIComponent(recipeId)}`, {
    method: "GET",
    accessToken,
  });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ recipeId: string }> },
) {
  const accessToken = bearerToken(request);
  if (!accessToken) return unauthenticated();
  const { recipeId } = await params;
  const body = await request.json();
  return proxyRequest(`${RECIPE_SERVICE_BASE_URL}/api/v1/recipes/${encodeURIComponent(recipeId)}`, {
    method: "PATCH",
    body,
    accessToken,
  });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ recipeId: string }> },
) {
  const accessToken = bearerToken(request);
  if (!accessToken) return unauthenticated();
  const { recipeId } = await params;
  return proxyRequest(`${RECIPE_SERVICE_BASE_URL}/api/v1/recipes/${encodeURIComponent(recipeId)}`, {
    method: "DELETE",
    accessToken,
  });
}
