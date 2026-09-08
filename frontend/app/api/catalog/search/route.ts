import type { NextRequest } from "next/server";
import { CATALOG_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();
  const q = searchParams.get("q");
  if (q) params.set("q", q);
  params.set("page", searchParams.get("page") ?? "1");
  params.set("page_size", searchParams.get("page_size") ?? "20");
  return proxyRequest(
    `${CATALOG_SERVICE_BASE_URL}/api/v1/catalog/products/search?${params.toString()}`,
    { method: "GET" },
  );
}
