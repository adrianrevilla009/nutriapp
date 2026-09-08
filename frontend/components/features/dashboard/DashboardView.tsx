"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useDashboard } from "@/lib/hooks/useDashboard";
import { todayLocalDateString } from "@/lib/date";
import { Button } from "@/components/ui/Button";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { MacroTotalsCard } from "@/components/features/dashboard/MacroTotalsCard";
import { MicronutrientTable } from "@/components/features/dashboard/MicronutrientTable";
import { TargetComparison } from "@/components/features/dashboard/TargetComparison";

export function DashboardView() {
  const t = useTranslations("dashboard");
  const tCommon = useTranslations("common");
  const [date] = useState(() => todayLocalDateString());
  const { data, isLoading, isError, refetch, isFetching } = useDashboard(date);

  return (
    <div className="page">
      <h1>{t("title")}</h1>
      <Button variant="secondary" onClick={() => void refetch()} disabled={isFetching}>
        {isFetching ? tCommon("loading") : t("refresh")}
      </Button>

      {isLoading ? <LoadingSkeleton label={tCommon("loading")} /> : null}
      {isError ? <ErrorBanner message={tCommon("genericError")} /> : null}

      {data ? (
        <>
          <MacroTotalsCard
            diarySummary={data.diary_summary}
            nutrientTotals={data.nutrient_totals}
          />
          <MicronutrientTable nutrientTotals={data.nutrient_totals} />
          <TargetComparison target={data.target} />
        </>
      ) : null}
    </div>
  );
}
