"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";
import { register } from "@/lib/api/identity";
import { RegisterRequestSchema } from "@/schemas/identity";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

export function RegisterForm() {
  const t = useTranslations("register");
  const tCommon = useTranslations("common");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => register(email, password),
    onSuccess: () => setRegisteredEmail(email),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setEmailError(null);
    setPasswordError(null);

    const result = RegisterRequestSchema.safeParse({ email, password });
    if (!result.success) {
      const flattened = result.error.flatten().fieldErrors;
      if (flattened.email) setEmailError(t("invalidEmail"));
      if (flattened.password) setPasswordError(t("passwordRequired"));
      return; // Blocked client-side -- no network call (test-plan section 3).
    }
    mutation.mutate();
  }

  if (registeredEmail) {
    return (
      <div className="notice">
        <h1>{t("successTitle")}</h1>
        <p>{t("successBody", { email: registeredEmail })}</p>
        <a href="/login">{t("loginLink")}</a>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>{t("title")}</h1>
      <form onSubmit={handleSubmit} noValidate>
        {mutation.isError ? (
          <ErrorBanner
            message={mutation.error instanceof Error ? mutation.error.message : t("genericError")}
          />
        ) : null}
        <TextField
          label={t("emailLabel")}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={emailError}
        />
        <TextField
          label={t("passwordLabel")}
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={passwordError}
        />
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? tCommon("loading") : t("submit")}
        </Button>
      </form>
      <a href="/login">{t("loginLink")}</a>
    </div>
  );
}
