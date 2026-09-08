import { useTranslations } from "next-intl";
import type { UnavailableReason } from "@/schemas/bff";

/**
 * Renders a distinct message per reason -- "still catching up" and
 * "couldn't be loaded" mean different things to the user and must not
 * collapse to identical text (test-plan section 3). Conveyed via visible
 * text, never color alone (accessibility-standards SKILL.md).
 */
export function SectionUnavailable({ reason }: { reason: UnavailableReason }) {
  const t = useTranslations("dashboard");
  const message =
    reason === "not_yet_computed"
      ? t("unavailableNotYetComputed")
      : t("unavailableDownstreamError");
  return (
    <p role="status" className="notice">
      {message}
    </p>
  );
}
