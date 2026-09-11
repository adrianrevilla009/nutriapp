"use client";

import { useQuery } from "@tanstack/react-query";
import { searchPublishedRecipes } from "@/lib/api/recipes";
import { useSession } from "@/lib/hooks/useSession";

export function useSearchRecipes(query: string) {
  const { accessToken, isAuthenticated } = useSession();
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["recipes", "search", trimmed],
    queryFn: () => searchPublishedRecipes(trimmed, accessToken as string),
    enabled: isAuthenticated && trimmed.length > 0,
    staleTime: 60 * 1000,
  });
}
