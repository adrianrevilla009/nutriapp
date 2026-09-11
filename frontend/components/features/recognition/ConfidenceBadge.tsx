import { useTranslations } from "next-intl";

/**
 * Confidence is ALWAYS a real number, in text, never color-only
 * (media-recognition-conventions SKILL.md's "confidence must always be
 * explicit" / accessibility-standards SKILL.md's "color is never the only
 * channel"). Deliberately does not re-derive food-recognition-service's
 * own FOOD_RECOGNITION_CONFIDENCE_THRESHOLD as a second, potentially
 * drifting frontend-side tier cutoff (journey 2 implementation plan
 * resolution 3) -- just the raw percentage.
 */
export function ConfidenceBadge({ confidence }: { confidence: number }) {
  const t = useTranslations("photoLog");
  const percent = Math.round(confidence * 100);
  return <span className="confidence-badge">{t("confidence", { percent })}</span>;
}
