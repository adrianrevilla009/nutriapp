"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";
import { useSession } from "@/lib/hooks/useSession";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

export function LoginForm() {
  const t = useTranslations("login");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const { login } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: () => router.push("/search"),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="page">
      <h1>{t("title")}</h1>
      <form onSubmit={handleSubmit} noValidate>
        {mutation.isError ? (
          // DELIBERATELY GENERIC, always -- never render the backend's own
          // message/code here. identity-service maps wrong-password,
          // unverified-email, and locked-account to the same
          // InvalidCredentialsError with no distinguishing signal
          // (application/commands/login.py); this UI must not invent a
          // distinction the API doesn't provide, and must stay generic even
          // if a future backend change ever did start distinguishing them.
          <ErrorBanner message={t("invalidCredentials")} />
        ) : null}
        <TextField
          label={t("emailLabel")}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label={t("passwordLabel")}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? tCommon("loading") : t("submit")}
        </Button>
      </form>
      <a href="/register">{t("registerLink")}</a>
    </div>
  );
}
