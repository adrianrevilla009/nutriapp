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
      <button type="button" className="btn btn-secondary" onClick={() => void logout()}>
        {t("logout")}
      </button>
    </nav>
  );
}
