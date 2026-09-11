"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteRecipe } from "@/lib/api/recipes";
import { useSession } from "@/lib/hooks/useSession";

export function useDeleteRecipe(recipeId: string) {
  const { accessToken } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => {
      if (!accessToken) throw new Error("Not authenticated.");
      return deleteRecipe(recipeId, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes", "mine"] });
    },
  });
}
