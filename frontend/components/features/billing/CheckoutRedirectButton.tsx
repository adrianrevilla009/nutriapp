"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCreateCheckoutSession } from "@/lib/hooks/useCreateCheckoutSession";
import { AlreadyProError } from "@/lib/api/billing";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

/**
 * Redirects the raw BROWSER to Stripe's hosted Checkout -- this app never
 * embeds a payment form (checkout_routes.py's own docstring: "never
 * collects card data itself", PCI scope minimization). journey-3
 * resolution 1: no live Stripe round-trip exists in this environment
 * (docker-compose.yml's Stripe keys are placeholders, tracked as
 * billing-service's own lead-time item) -- this component's own
 * responsibility ends at correctly relaying checkout_url; completing the
 * Stripe leg itself is outside this app's test coverage by design (covered
 * only by this component's own integration test, never a live E2E round
 * trip).
 */
export function CheckoutRedirectButton() {
  const t = useTranslations("pro");
  const router = useRouter();
  const mutation = useCreateCheckoutSession();

  function handleClick() {
    const base =
      process.env.NEXT_PUBLIC_APP_BASE_URL ??
      (typeof window !== "undefined" ? window.location.origin : "");
    mutation.mutate(
      { successUrl: `${base}/pro/success`, cancelUrl: `${base}/pro/cancel` },
      {
        onSuccess: (result) => {
          window.location.assign(result.checkout_url);
        },
        onError: (err) => {
          if (err instanceof AlreadyProError) {
            router.push("/recipes?alreadyPro=1");
          }
        },
      },
    );
  }

  // A 409/AlreadyProError is handled by the redirect above, not the error
  // banner -- the banner is reserved for a genuine failure to start
  // checkout (test-plan section 3's contrast requirement).
  const showGenericError = mutation.isError && !(mutation.error instanceof AlreadyProError);

  return (
    <div>
      {showGenericError ? <ErrorBanner message={t("checkoutError")} /> : null}
      <Button type="button" onClick={handleClick} disabled={mutation.isPending}>
        {mutation.isPending ? t("redirecting") : t("upgradeAction")}
      </Button>
    </div>
  );
}
