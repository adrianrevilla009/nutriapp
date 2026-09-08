/**
 * Browser-facing bff client -- calls this app's own app/api/bff/dashboard
 * Route Handler (implementation plan resolution 1), which forwards the
 * caller's access token to bff-service's authenticated
 * GET /api/v1/bff/dashboard.
 */
import { apiFetch } from "@/lib/api/http-client";
import { DashboardResponseSchema, type DashboardResponse } from "@/schemas/bff";

export async function getDashboard(date: string, accessToken: string): Promise<DashboardResponse> {
  const raw = await apiFetch<unknown>(`/api/bff/dashboard?date=${encodeURIComponent(date)}`, {
    accessToken,
  });
  return DashboardResponseSchema.parse(raw);
}
