"use client";

import { useQuery } from "@tanstack/react-query";
import { listOwnRecipes } from "@/lib/api/recipes";
import { useSession } from "@/lib/hooks/useSession";

export function useOwnRecipes() {
  const { accessToken, isAuthenticated } = useSession();
  return useQuery({
    queryKey: ["recipes", "mine"],
    queryFn: () => listOwnRecipes(accessToken as string),
    enabled: isAuthenticated,
  });
}
