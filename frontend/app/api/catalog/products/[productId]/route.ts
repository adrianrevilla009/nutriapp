import { CATALOG_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { proxyRequest } from "@/lib/server/proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ productId: string }> },
) {
  const { productId } = await params;
  return proxyRequest(
    `${CATALOG_SERVICE_BASE_URL}/api/v1/catalog/products/${encodeURIComponent(productId)}`,
    { method: "GET" },
  );
}
