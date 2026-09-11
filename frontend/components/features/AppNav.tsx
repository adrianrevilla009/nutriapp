"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useSession } from "@/lib/hooks/useSession";

export function AppNav() {
  const t = useTranslations("nav");
  const { isAuthenticated, logout } = useSession();

  if (!isAuthenticated) return null;

  return (
    <nav className="app-nav" aria-label="Main">
      <Link href="/search">{t("search")}</Link>
      <Link href="/log/photo">{t("logPhoto")}</Link>
      <Link href="/dashboard">{t("dashboard")}</Link>
      {/* journey 3: shown UNCONDITIONALLY, even to an already-Pro user --
          resolution 3: billing-service exposes no user-facing entitlement
          endpoint, so this app has no reliable client-side "Pro badge" to
          branch on. The actual gate is discovered by attempting a
          Pro-gated action and handling its 402, not by hiding these links. */}
      <Link href="/recipes">{t("recipes")}</Link>
      <Link href="/pro">{t("upgradeToPro")}</Link>
      <button type="button" className="btn btn-secondary" onClick={() => void logout()}>
        {t("logout")}
      </button>
    </nav>
  );
}
