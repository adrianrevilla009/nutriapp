"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createRecipe } from "@/lib/api/recipes";
import { useSession } from "@/lib/hooks/useSession";
import type { RecipeMutationRequest } from "@/schemas/recipe";

export function useCreateRecipe() {
  const { accessToken } = useSession();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: RecipeMutationRequest) => {
      if (!accessToken) throw new Error("Not authenticated.");
      return createRecipe(request, accessToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes", "mine"] });
    },
  });
}
