import { NextResponse, type NextRequest } from "next/server";
import { BFF_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

function bearerToken(request: NextRequest): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice("Bearer ".length).trim() || null;
}

export async function GET(request: NextRequest) {
  const accessToken = bearerToken(request);
  if (!accessToken) {
    return NextResponse.json(
      { error: "Missing authenticated caller.", code: "UNAUTHENTICATED" },
      { status: 401 },
    );
  }
  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date");
  if (!date) {
    return NextResponse.json({ error: "Missing date.", code: "MISSING_DATE" }, { status: 400 });
  }
  return proxyRequest(
    `${BFF_SERVICE_BASE_URL}/api/v1/bff/dashboard?date=${encodeURIComponent(date)}`,
    { method: "GET", accessToken },
  );
}
