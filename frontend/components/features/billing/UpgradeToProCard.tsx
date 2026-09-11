import { useTranslations } from "next-intl";
import { CheckoutRedirectButton } from "@/components/features/billing/CheckoutRedirectButton";

export function UpgradeToProCard() {
  const t = useTranslations("pro");
  return (
    <div className="page">
      <h1>{t("title")}</h1>
      <p>{t("pitch")}</p>
      <CheckoutRedirectButton />
    </div>
  );
}
