"use client";

import { useMutation } from "@tanstack/react-query";
import { createCheckoutSession, type CreateCheckoutSessionParams } from "@/lib/api/billing";
import { useSession } from "@/lib/hooks/useSession";

export function useCreateCheckoutSession() {
  const { accessToken } = useSession();

  return useMutation({
    mutationFn: (params: CreateCheckoutSessionParams) => {
      if (!accessToken) {
        throw new Error("Not authenticated.");
      }
      return createCheckoutSession(params, accessToken);
    },
  });
}
