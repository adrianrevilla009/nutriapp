import Link from "next/link";
import { useTranslations } from "next-intl";

/**
 * journey-3 resolution 3: billing-service has no user-facing "am I Pro
 * now?" endpoint -- this copy is deliberately honest ("payment received,
 * activation can take a moment"), never a false "You're now Pro!"
 * confirmation this app has no way to actually verify.
 */
export function ProSuccessBanner({ sessionId }: { sessionId?: string }) {
  const t = useTranslations("pro");
  return (
    <div className="notice">
      <h1>{t("successTitle")}</h1>
      <p>{t("successBody")}</p>
      {/* Not rendered as visible copy (resolution 3: this app has no way to
          verify anything against it) -- kept only as a diagnostic hook, so
          Stripe's own session_id is at least inspectable/loggable if a
          support case ever needs it. */}
      <div hidden data-stripe-session-id={sessionId ?? undefined} />
      <Link href="/recipes/new" className="btn btn-primary">
        {t("successCta")}
      </Link>
    </div>
  );
}
