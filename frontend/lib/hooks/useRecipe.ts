"use client";

import { useQuery } from "@tanstack/react-query";
import { getRecipe } from "@/lib/api/recipes";
import { useSession } from "@/lib/hooks/useSession";

export function useRecipe(recipeId: string) {
  const { accessToken, isAuthenticated } = useSession();
  return useQuery({
    queryKey: ["recipes", recipeId],
    queryFn: () => getRecipe(recipeId, accessToken as string),
    enabled: isAuthenticated && recipeId.length > 0,
  });
}
