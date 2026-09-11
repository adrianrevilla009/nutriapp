"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { usePublishRecipe } from "@/lib/hooks/usePublishRecipe";
import { NotEntitledError } from "@/lib/api/recipes";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

/**
 * CLAUDE.md section 8: publishing makes a recipe visible to OTHER users --
 * a distinct consent surface from general ToS acceptance, not a bare
 * "Publish" button. The confirmation step below gates EVERY API call: no
 * network call happens until the user explicitly acknowledges this
 * specific copy (journey-3 test-plan section 3's explicit "zero API
 * calls" assertion).
 */
export function PublishRecipeButton({ recipeId }: { recipeId: string }) {
  const t = useTranslations("recipes");
  const [confirming, setConfirming] = useState(false);
  const mutation = usePublishRecipe(recipeId);

  function handleConfirmedPublish() {
    mutation.mutate();
    setConfirming(false);
  }

  // Distinguishable via `instanceof`, per test-plan section 2/3 -- never a
  // string-match on `.code`.
  const isNotEntitled = mutation.error instanceof NotEntitledError;
  const isOtherError = mutation.isError && !isNotEntitled;

  if (confirming) {
    return (
      <div className="notice" role="group" aria-label={t("publishConfirmHeading")}>
        <p>{t("publishConsentCopy")}</p>
        <Button type="button" onClick={handleConfirmedPublish}>
          {t("publishConfirmAction")}
        </Button>
        <Button type="button" variant="secondary" onClick={() => setConfirming(false)}>
          {t("publishConfirmCancel")}
        </Button>
      </div>
    );
  }

  return (
    <div>
      {isNotEntitled ? (
        <div className="notice">
          <p>{t("publishNotEntitled")}</p>
          <Link href="/pro" className="btn btn-primary">
            {t("upgradeAction")}
          </Link>
        </div>
      ) : null}
      {isOtherError ? (
        <ErrorBanner
          message={mutation.error instanceof Error ? mutation.error.message : t("publishError")}
        />
      ) : null}
      <Button type="button" onClick={() => setConfirming(true)} disabled={mutation.isPending}>
        {mutation.isPending ? t("publishing") : t("publishAction")}
      </Button>
    </div>
  );
}
