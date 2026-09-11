"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { publishRecipe } from "@/lib/api/recipes";
import { useSession } from "@/lib/hooks/useSession";

export function usePublishRecipe(recipeId: string) {
  const { accessToken } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => {
      if (!accessToken) throw new Error("Not authenticated.");
      return publishRecipe(recipeId, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["recipes", recipeId] });
    },
  });
}
