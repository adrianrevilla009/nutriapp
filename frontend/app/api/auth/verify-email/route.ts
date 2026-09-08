import type { NextRequest } from "next/server";
import { IDENTITY_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyRequest(`${IDENTITY_SERVICE_BASE_URL}/api/v1/auth/verify-email`, {
    method: "POST",
    body,
  });
}
