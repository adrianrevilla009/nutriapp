import Link from "next/link";
import { useTranslations } from "next-intl";

export function ProCancelBanner() {
  const t = useTranslations("pro");
  return (
    <div className="notice">
      <h1>{t("cancelTitle")}</h1>
      <p>{t("cancelBody")}</p>
      <Link href="/pro" className="btn btn-secondary">
        {t("cancelCta")}
      </Link>
    </div>
  );
}
