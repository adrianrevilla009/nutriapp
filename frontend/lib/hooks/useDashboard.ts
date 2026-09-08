"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboard } from "@/lib/api/bff";
import { useSession } from "@/lib/hooks/useSession";

export function useDashboard(date: string) {
  const { accessToken } = useSession();
  return useQuery({
    queryKey: ["bff", "dashboard", date],
    queryFn: () => {
      if (!accessToken) {
        throw new Error("Not authenticated.");
      }
      return getDashboard(date, accessToken);
    },
    enabled: accessToken !== null,
    // Deliberately short -- this screen surfaces diary-service's own
    // async-projection lag rather than hiding it (implementation plan
    // section 5), so a short staleTime plus the manual refresh button
    // gives the user a real way to check again without a full reload.
    staleTime: 15 * 1000,
  });
}
