"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { logFoodEntry } from "@/lib/api/diary";
import { useSession } from "@/lib/hooks/useSession";
import type { LogFoodEntryRequest } from "@/schemas/diary";

export interface LogFoodEntryVariables {
  request: LogFoodEntryRequest;
  /** Journey 2: set to the food-recognition analysis_id for an
   * ai_detected-sourced entry, forwarded as X-Correlation-Id
   * (architecture-agent finding) -- omitted for a plain catalog_product
   * entry, same as journey 1's original behavior. */
  correlationId?: string;
}

export function useLogFoodEntry() {
  const { accessToken } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ request, correlationId }: LogFoodEntryVariables) => {
      if (!accessToken) {
        throw new Error("Not authenticated.");
      }
      return logFoodEntry(request, accessToken, correlationId);
    },
    onSuccess: () => {
      // Marks the dashboard query stale so the manual "Refresh" affordance
      // (implementation plan section 5) fetches fresh data on demand --
      // this does NOT force an immediate refetch, since diary-service's
      // async projection lag means an immediate refetch would likely still
      // show pre-log totals anyway (see components/features/dashboard).
      queryClient.invalidateQueries({ queryKey: ["bff", "dashboard"] });
    },
  });
}
