"use client";

import { useMutation } from "@tanstack/react-query";
import { analyzeFoodPhoto } from "@/lib/api/food-recognition";
import { useSession } from "@/lib/hooks/useSession";

/**
 * Unlike useLogFoodEntry, this hook never invalidates any TanStack Query
 * cache key -- a photo analysis has no downstream read model to
 * invalidate (journey 2 test-plan section 3).
 */
export function useAnalyzePhoto() {
  const { accessToken } = useSession();

  return useMutation({
    mutationFn: (file: File) => {
      if (!accessToken) {
        throw new Error("Not authenticated.");
      }
      return analyzeFoodPhoto(file, accessToken);
    },
  });
}
