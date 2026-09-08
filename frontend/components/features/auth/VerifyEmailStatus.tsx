"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { verifyEmail } from "@/lib/api/identity";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

type Status = "invalid_link" | "loading" | "success" | "failure";

export function VerifyEmailStatus() {
  const t = useTranslations("verifyEmail");
  const searchParams = useSearchParams();
  const referenceId = searchParams.get("reference_id");
  const secret = searchParams.get("secret");

  const [status, setStatus] = useState<Status>(referenceId && secret ? "loading" : "invalid_link");
  // Guards a real React-effect double-invoke bug class (StrictMode
  // remounts effects once in dev) -- verify-email must be called exactly
  // once (test-plan section 3).
  const calledRef = useRef(false);

  useEffect(() => {
    if (status !== "loading" || calledRef.current) return;
    calledRef.current = true;
    verifyEmail(referenceId as string, secret as string)
      .then(() => setStatus("success"))
      .catch(() => setStatus("failure"));
  }, [status, referenceId, secret]);

  if (status === "invalid_link") {
    return <ErrorBanner message={t("invalidLink")} />;
  }
  if (status === "loading") {
    return <LoadingSkeleton label={t("title")} />;
  }
  if (status === "failure") {
    return (
      <div>
        <ErrorBanner message={t("failure")} />
        <a href="/login">{t("loginLink")}</a>
      </div>
    );
  }
  return (
    <div className="notice">
      <p>{t("success")}</p>
      <a href="/login">{t("loginLink")}</a>
    </div>
  );
}
